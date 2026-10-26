#!/usr/bin/env python3
"""
Python Flask Backend for mRNAviewer
替代原本的Covariant Script后端，提供兼容的API接口
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import base64
import uuid
import time
import threading
import subprocess
import os
import re
import shutil
from pathlib import Path
import sys
from contextlib import contextmanager

app = Flask(__name__, static_folder='frontend/mRNAviewer', static_url_path='')
CORS(app)

# 配置路径
BASE_DIR = Path(__file__).parent
WORKSPACE_DIR = BASE_DIR / "workspace"
CODON_DIR = WORKSPACE_DIR / "codon"
RESULT_RETENTION_SECONDS = int(os.environ.get("MRNAVIEWER_RESULT_RETENTION_SECONDS", "86400"))
ORPHAN_RETENTION_SECONDS = max(RESULT_RETENTION_SECONDS * 2, RESULT_RETENTION_SECONDS + 3600)
TASK_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{3}\Z")
MANAGED_MARKER = ".mrnaviewer-managed"
FINISHED_MARKER = ".mrnaviewer-finished"

# Tissue类型列表（与前端对应）
TISSUES = ['general', 'Adrenal_gland', 'Appendix', 'Brain', 'Colon', 'Duodenum', 'Endometrium', 'Esophagus', 'Fallopian_tube', 'Fat', 'Gallbladder', 'Heart', 'Kidney', 'Liver', 'Lung', 'Lymph_node', 'Ovary', 'Pancreas', 'Placenta', 'Prostate', 'Rectum', 'Salivary_gland', 'Small_intestine', 'Smooth_muscle', 'Spleen', 'Stomach', 'Testis', 'Thyroid', 'Tonsil', 'Urinary_bladder']

# 任务存储 (简化版，不使用数据库)
tasks = {}
task_lock = threading.Lock()
rnafold_lock = threading.Lock()
gen_image_lock = threading.Lock()
blast_lock = threading.Lock()


def query_gpus():
    """Read physical GPU indexes, UUIDs, free memory, and utilization."""
    result = subprocess.run(
        ["/usr/bin/nvidia-smi", "--query-gpu=index,uuid,memory.free,utilization.gpu",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    )
    gpus = []
    for line in result.stdout.splitlines():
        index, uuid, free_mb, utilization = (part.strip() for part in line.split(","))
        index = int(index)
        if index in (0, 1):
            gpus.append({
                "index": index,
                "uuid": uuid,
                "free_mb": int(free_mb),
                "utilization": int(utilization),
            })
    if not gpus:
        raise RuntimeError("No usable GPU 0 or GPU 1 found")
    return gpus


class GpuScheduler:
    """Reserve at most one mRNAviewer model process on each physical GPU."""

    def __init__(self, probe=query_gpus):
        self.probe = probe
        self.condition = threading.Condition()
        self.reserved = set()

    @contextmanager
    def lease(self):
        with self.condition:
            while True:
                available = [gpu for gpu in self.probe()
                             if gpu["index"] not in self.reserved]
                if available:
                    # More free VRAM wins, then lower utilization; GPU 1 wins ties.
                    chosen = max(available, key=lambda gpu: (
                        gpu["free_mb"], -gpu["utilization"], gpu["index"]
                    ))
                    self.reserved.add(chosen["index"])
                    break
                self.condition.wait()
        try:
            yield chosen
        finally:
            with self.condition:
                self.reserved.remove(chosen["index"])
                self.condition.notify_all()


gpu_scheduler = GpuScheduler()


def managed_task_dir(task_id):
    """Only return directories created under the codon task root."""
    if not TASK_ID_PATTERN.fullmatch(task_id):
        return None
    directory = CODON_DIR / "tasks" / task_id
    if directory.is_symlink() or not directory.is_dir():
        return None
    marker = directory / MANAGED_MARKER
    if marker.is_symlink() or not marker.is_file():
        return None
    return directory


def finish_task(task_id, task_dir=None):
    """Start the download window when computation ends, including failures."""
    with task_lock:
        task = tasks.get(task_id)
        if task is None:
            return
        task.finished_at = time.time()
        finished_at = task.finished_at

    if task_dir is not None and managed_task_dir(task_id) == task_dir:
        try:
            pending = task_dir / (FINISHED_MARKER + ".tmp")
            pending.write_text(str(finished_at), encoding="ascii")
            os.replace(pending, task_dir / FINISHED_MARKER)
        except OSError:
            app.logger.exception("Could not record completion time for task %s", task_id)


def cleanup_expired_tasks(now=None):
    """Remove expired results and only disk directories marked as managed."""
    now = time.time() if now is None else now
    with task_lock:
        expired_ids = set()
        for task_id, task in list(tasks.items()):
            finished_at = getattr(task, "finished_at", None)
            if finished_at is not None and now - finished_at >= RESULT_RETENTION_SECONDS:
                expired_ids.add(task_id)
                del tasks[task_id]
        active_ids = set(tasks)
        remaining = [[task_id, STATE_MAP.get(task.state, task.state)]
                     for task_id, task in tasks.items()]

    task_root = CODON_DIR / "tasks"
    if task_root.is_dir():
        for directory in task_root.iterdir():
            if directory.name in active_ids:
                continue
            managed = managed_task_dir(directory.name)
            if managed is None:
                continue
            try:
                finished_marker = managed / FINISHED_MARKER
                if directory.name in expired_ids:
                    expired = True
                elif finished_marker.is_file() and not finished_marker.is_symlink():
                    finished_at = float(finished_marker.read_text(encoding="ascii"))
                    expired = now - finished_at >= RESULT_RETENTION_SECONDS
                else:
                    # A worker that dies before completion cannot write a finish marker.
                    expired = now - (managed / MANAGED_MARKER).stat().st_mtime >= ORPHAN_RETENTION_SECONDS
                if expired:
                    shutil.rmtree(managed)
            except (OSError, ValueError):
                app.logger.exception("Could not clean task directory %s", managed)
    return remaining


def serialized(lock):
    """Keep scripts with fixed input and output paths from overlapping."""
    def decorate(func):
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper
    return decorate

# 状态映射
STATE_MAP = {
    "PREPARE": "Booting...",
    "QUEUED": "Waiting for GPU...",
    "WORKING": "Analyzing...",
    "DONE": "Done"
}

class Task:
    def __init__(self, task_id, data, tissue):
        self.id = task_id
        self.state = "PREPARE"
        self.data = data
        self.tissue = tissue
        self.result = None
        self.images = {}
        self.mfe = {}
        self.created_at = time.time()
        self.finished_at = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "state": self.state,
            "data": self.data,
            "tissue": self.tissue,
            "result": self.result,
            "created_at": self.created_at,
            "finished_at": self.finished_at
        }


def run_optimization(task_id):
    """在后台运行密码子优化"""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return
        task.state = "QUEUED"
    
    print(f"[Task {task_id}] Starting optimization with tissue: {task.tissue}")
    
    task_dir = None
    try:
        # 为每个任务创建独立的工作目录
        task_dir = CODON_DIR / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=False)
        (task_dir / MANAGED_MARKER).write_text(str(task.created_at), encoding="ascii")
        
        # 写入输入文件到任务专属目录
        input_file = task_dir / "input.txt"
        input_file.write_text(task.data)
        print(f"[Task {task_id}] Input file written: {input_file}")
        
        # 根据tissue类型生成对应的config文件到任务专属目录
        config_file = task_dir / "decode.config"
        
        # 确定模型路径
        if task.tissue == "general" or task.tissue == "0":
            # 使用默认general模型
            model_path = "./lstmcrf.113.model"
            # dset_path = "./lstmcrf.dset"
        else:
            # 使用tissue特定模型
            model_path = f"./cds_tissue_model/{task.tissue}/lstmcrf.model"
            # dset_path = f"./cds_tissue_model/{task.tissue}/lstmcrf.dset"
        
        # 生成config文件（使用相对于任务目录的路径）
        config_content = f"""### Decode ###
status=decode
raw_dir=tasks/{task_id}/input.txt

nbest=1
decode_dir=tasks/{task_id}/output.out

dset_dir=./lstmcrf_1500.dset
load_model_dir={model_path}


#python main.py --config tasks/{task_id}/decode.config
"""
        config_file.write_text(config_content)
        print(f"[Task {task_id}] Config file generated with model: {model_path}")
        
        json_out = task_dir / "output_json.out"
        with gpu_scheduler.lease() as gpu:
            with task_lock:
                task.state = "WORKING"
            print(f"[Task {task_id}] Assigned physical GPU {gpu['index']}", flush=True)
            inference_env = os.environ.copy()
            inference_env["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
            result = subprocess.run(
                [sys.executable, "main.py", "--config", f"tasks/{task_id}/decode.config",
                 "--tissue", task.tissue],
                cwd=CODON_DIR,
                env=inference_env,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        print(f"[Task {task_id}] Optimization completed with returncode: {result.returncode}")
        if result.returncode != 0:
            raise RuntimeError(f"Inference failed: {result.stderr[-2000:]}")
        if json_out.exists():
            result_data = json.loads(json_out.read_text())
            print(f"[Task {task_id}] JSON output loaded: {len(result_data)} parts")
            
            # 读取各部分序列
            full_seq = result_data[0] + result_data[1] + result_data[2]
            print(f"[Task {task_id}] Full sequence length: {len(full_seq)}")
            
            # 运行RNAfold生成图像和MFE
            print(f"[Task {task_id}] Running RNAfold for FULL...")
            run_rnafold(task_id, full_seq, "full")
            print(f"[Task {task_id}] Running RNAfold for 5UTR...")
            run_rnafold(task_id, result_data[0], "5utr")
            print(f"[Task {task_id}] Running RNAfold for ORF...")
            run_rnafold(task_id, result_data[1], "orf")
            print(f"[Task {task_id}] Running RNAfold for 3UTR...")
            run_rnafold(task_id, result_data[2], "3utr")
            
            print(f"[Task {task_id}] MFE values: {task.mfe}")
            
            # 构建结果 - MFE必须是数组格式，按照 [full, 5utr, orf, 3utr] 顺序
            mfe_array = [
                task.mfe.get('full', '0'),
                task.mfe.get('5utr', '0'),
                task.mfe.get('orf', '0'),
                task.mfe.get('3utr', '0')
            ]
            result_obj = {
                "seq": [full_seq] + result_data,
                "mfe": mfe_array
            }
            
            with task_lock:
                task.result = base64.b64encode(json.dumps(result_obj).encode()).decode()
                task.state = "DONE"
                print(f"[Task {task_id}] Task completed successfully!")
        else:
            print(f"[Task {task_id}] ERROR: JSON output file not found!")
            with task_lock:
                task.state = "ERROR"
                
    except Exception as e:
        print(f"Error in optimization: {e}")
        import traceback
        traceback.print_exc()
        with task_lock:
            task.state = "ERROR"
    finally:
        finish_task(task_id, task_dir)


@serialized(rnafold_lock)
def run_rnafold(task_id, sequence, region):
    """运行RNAfold进行二级结构预测"""
    rnafold_dir = WORKSPACE_DIR / "rnafold"
    input_file = rnafold_dir / "input.txt"
    output_dir = rnafold_dir / "output"
    try:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        # 写入输入文件
        input_file.write_text(sequence)
        
        # 运行RNAfold
        result = subprocess.run(
            ["bash", "main.sh", str(input_file)],
            cwd=str(rnafold_dir),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:])

        # 读取输出
        image_file = output_dir / "image.png"
        mfe_file = output_dir / "mfe.txt"
        
        if image_file.exists():
            with open(image_file, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
                with task_lock:
                    task = tasks.get(task_id)
                    if task:
                        task.images[region] = image_data
        
        if mfe_file.exists():
            mfe_value = mfe_file.read_text().strip()
            with task_lock:
                task = tasks.get(task_id)
                if task:
                    task.mfe[region] = mfe_value
        
    except Exception as e:
        print(f"Error in RNAfold for {region}: {e}")
    finally:
        input_file.unlink(missing_ok=True)
        (rnafold_dir / "fold.log").unlink(missing_ok=True)
        if output_dir.exists():
            shutil.rmtree(output_dir)


@app.route('/')
def index():
    """主页"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """提供静态文件"""
    return send_from_directory(app.static_folder, path)


@app.route('/backend/executor/submit', methods=['POST'])
def submit():
    """提交新任务"""
    data = request.get_json(force=True)  # 强制解析JSON
    sequence = data.get('data', '')
    tissue_name = data.get('tissue', 'general')
    
    # 验证tissue名称是否合法
    if tissue_name not in TISSUES:
        tissue_name = 'general'
    
    print(f"[Submit] Received tissue_name={tissue_name}")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:12]
    
    # 创建任务
    task = Task(task_id, sequence, tissue_name)
    
    with task_lock:
        tasks[task_id] = task
    
    # 在后台线程中运行优化
    thread = threading.Thread(target=run_optimization, args=(task_id,))
    thread.daemon = True
    thread.start()
    
    return task_id


@app.route('/backend/executor/queueing', methods=['POST'])
def queueing():
    """查询所有任务状态"""
    with task_lock:
        result = []
        for task_id, task in tasks.items():
            mapped_state = STATE_MAP.get(task.state, task.state)
            # 返回 [task_id, state, tissue] 以便前端显示Type列
            tissue = getattr(task, 'tissue', 'general')  # 默认值，兼容旧任务
            result.append([task_id, mapped_state, tissue])
            print(f"[Queueing] Task {task_id}: state={task.state}, mapped={mapped_state}, tissue={tissue}")
    
    # 返回JSON字符串，让前端自己parse（保持与原始后端一致）
    return json.dumps(result)


@app.route('/backend/executor/result', methods=['POST'])
def get_result():
    """获取任务结果"""
    data = request.get_json(force=True)
    task_id = data.get('id', '')
    
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return "NULL"
        
        if task.state == "DONE":
            return task.result or "NULL"
        else:
            return task.state


@app.route('/backend/executor/image_full', methods=['POST'])
def image_full():
    """获取完整序列的图像"""
    data = request.get_json(force=True)
    task_id = data.get('id', '')
    
    with task_lock:
        task = tasks.get(task_id)
        if not task or 'full' not in task.images:
            return "NULL"
        return task.images['full']


@app.route('/backend/executor/image_5utr', methods=['POST'])
def image_5utr():
    """获取5'UTR的图像"""
    data = request.get_json(force=True)
    task_id = data.get('id', '')
    
    with task_lock:
        task = tasks.get(task_id)
        if not task or '5utr' not in task.images:
            return "NULL"
        return task.images['5utr']


@app.route('/backend/executor/image_orf', methods=['POST'])
def image_orf():
    """获取ORF的图像"""
    data = request.get_json(force=True)
    task_id = data.get('id', '')
    
    with task_lock:
        task = tasks.get(task_id)
        if not task or 'orf' not in task.images:
            return "NULL"
        return task.images['orf']


@app.route('/backend/executor/image_3utr', methods=['POST'])
def image_3utr():
    """获取3'UTR的图像"""
    data = request.get_json(force=True)
    task_id = data.get('id', '')
    
    with task_lock:
        task = tasks.get(task_id)
        if not task or '3utr' not in task.images:
            return "NULL"
        return task.images['3utr']


@app.route('/backend/executor/retiring', methods=['POST'])
def retiring():
    """Clean expired memory and disk results; called by the GPU server cron."""
    return jsonify(cleanup_expired_tasks())


@app.route('/backend/executor/gen_image', methods=['POST'])
def gen_image():
    """生成单个序列的二级结构图像"""
    data = request.get_json(force=True)
    sequence = data.get('data', '')
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:12]
    
    # 创建简单的任务对象
    image_task = type('obj', (object,), {
        'id': task_id,
        'state': 'PREPARE',
        'sequence': sequence,
        'mfe': None,
        'image': None,
        'created_at': time.time(),
        'finished_at': None
    })()
    
    with task_lock:
        tasks[task_id] = image_task
    
    print(f"[GEN_IMAGE {task_id}] Task created and added to tasks dict")
    
    # 后台运行RNAfold
    @serialized(gen_image_lock)
    def run_image_gen():
        print(f"[GEN_IMAGE {task_id}] Thread starting...")
        with task_lock:
            task = tasks.get(task_id)
            if not task:
                print(f"[GEN_IMAGE {task_id}] ERROR: Task not found in tasks dict!")
                return
            task.state = 'WORKING'
        
        print(f"[GEN_IMAGE {task_id}] Starting RNAfold analysis...")
        print(f"[GEN_IMAGE {task_id}] Sequence length: {len(sequence)}")
        rnafold_dir = WORKSPACE_DIR / "gen_image"
        input_file = rnafold_dir / "input.txt"
        output_dir = rnafold_dir / "output"
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            input_file.write_text(sequence)
            
            print(f"[GEN_IMAGE {task_id}] Running main.sh in {rnafold_dir}")
            
            result = subprocess.run(
                ["bash", "main.sh", str(input_file)],
                cwd=str(rnafold_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            print(f"[GEN_IMAGE {task_id}] RNAfold completed with returncode: {result.returncode}")
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:])

            image_file = output_dir / "image.png"
            mfe_file = output_dir / "mfe.txt"
            
            print(f"[GEN_IMAGE {task_id}] Checking output files...")
            print(f"[GEN_IMAGE {task_id}] Image exists: {image_file.exists()}")
            print(f"[GEN_IMAGE {task_id}] MFE exists: {mfe_file.exists()}")
            
            if image_file.exists() and mfe_file.exists():
                with open(image_file, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode()
                mfe_value = mfe_file.read_text().strip()
                
                with task_lock:
                    task.image = image_data
                    task.mfe = mfe_value
                    task.state = 'DONE'
                
                print(f"[GEN_IMAGE {task_id}] Results ready, MFE: {mfe_value}")
                
            else:
                print(f"[GEN_IMAGE {task_id}] ERROR: Output files missing!")
                with task_lock:
                    task.state = 'ERROR'
                    
        except Exception as e:
            print(f"[GEN_IMAGE {task_id}] Error: {e}")
            import traceback
            traceback.print_exc()
            with task_lock:
                task.state = 'ERROR'
        finally:
            try:
                input_file.unlink(missing_ok=True)
                (rnafold_dir / "fold.log").unlink(missing_ok=True)
                if output_dir.exists():
                    shutil.rmtree(output_dir)
            finally:
                finish_task(task_id)
    
    thread = threading.Thread(target=run_image_gen)
    thread.daemon = True
    
    try:
        thread.start()
        print(f"[GEN_IMAGE {task_id}] Thread started successfully")
    except Exception as e:
        print(f"[GEN_IMAGE {task_id}] Failed to start thread: {e}")
        with task_lock:
            image_task.state = 'ERROR'
        finish_task(task_id)
    
    return task_id


@app.route('/backend/executor/get_mfe', methods=['POST'])
def get_mfe():
    """获取MFE值"""
    data = request.get_json(force=True)
    task_id = data.get('id', '').strip()
    
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return "NULL"
        
        if task.state == 'DONE' and hasattr(task, 'mfe') and task.mfe:
            return task.mfe
        elif task.state == 'WORKING':
            return "WORKING"
        else:
            return "NULL"


@app.route('/backend/executor/get_image', methods=['POST'])
def get_image():
    """获取生成的图像"""
    data = request.get_json(force=True)
    task_id = data.get('id', '').strip()
    
    with task_lock:
        task = tasks.get(task_id)
        if not task or not hasattr(task, 'image') or not task.image:
            return "NULL"
        return task.image


@app.route('/backend/executor/blast_submit', methods=['POST'])
def blast_submit():
    """提交BLAST分析"""
    data = request.get_json(force=True)
    sequence = data.get('data', '')
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:12]
    
    # 创建任务对象
    blast_task = type('obj', (object,), {
        'id': task_id,
        'state': 'PREPARE',
        'sequence': sequence,
        'results': None,
        'created_at': time.time(),
        'finished_at': None
    })()
    
    with task_lock:
        tasks[task_id] = blast_task
    
    print(f"[BLAST {task_id}] Task created and added to tasks dict")
    
    # 后台运行BLAST分析
    @serialized(blast_lock)
    def run_blast_analysis():
        print(f"[BLAST {task_id}] Thread starting...")
        with task_lock:
            task = tasks.get(task_id)
            if not task:
                print(f"[BLAST {task_id}] ERROR: Task not found in tasks dict!")
                print(f"[BLAST {task_id}] Available task IDs: {list(tasks.keys())}")
                return
            task.state = 'WORKING'
        
        print(f"[BLAST {task_id}] Starting BLAST analysis...")
        blast_dir = WORKSPACE_DIR / "blast"
        query_file = blast_dir / "query.fa"
        query_dna_file = blast_dir / "query_dna.fa"
        output_dir = blast_dir / "output"
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            query_file.write_text(sequence)
            
            # 检查是否有blastn命令 (BLAST+)
            blastn_bin = os.environ.get("MRNAVIEWER_BLASTN_BIN", "blastn")
            if not shutil.which(blastn_bin):
                raise RuntimeError(f"BLAST executable is unavailable: {blastn_bin}")
            
            # 运行BLAST分析
            result = subprocess.run(
                ["bash", "main.sh"],
                cwd=str(blast_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            print(f"[BLAST {task_id}] BLAST completed with returncode: {result.returncode}")
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:])

            # 读取结果文件并编码
            files = ['hairpin.out', 'mature.out', 'result.out', 
                    'acc_hairpin.out', 'acc_mature.out', 'hyperlink.out']
            
            encoded_results = []
            for filename in files:
                filepath = output_dir / filename
                if filepath.exists():
                    with open(filepath, 'rb') as f:
                        encoded = base64.b64encode(f.read()).decode()
                        encoded_results.append(encoded)
                else:
                    encoded_results.append("")
            
            # 构建JSON数组字符串
            results_json = json.dumps(encoded_results)
            
            with task_lock:
                task.results = results_json
                task.state = 'DONE'
            
            print(f"[BLAST {task_id}] Results ready")
            
        except Exception as e:
            print(f"[BLAST {task_id}] Error: {e}")
            import traceback
            traceback.print_exc()
            with task_lock:
                task.state = 'ERROR'
        finally:
            try:
                query_file.unlink(missing_ok=True)
                query_dna_file.unlink(missing_ok=True)
                if output_dir.exists():
                    shutil.rmtree(output_dir)
            finally:
                finish_task(task_id)
    
    thread = threading.Thread(target=run_blast_analysis)
    thread.daemon = True
    try:
        thread.start()
    except Exception:
        with task_lock:
            blast_task.state = 'ERROR'
        finish_task(task_id)
        raise
    
    return task_id


@app.route('/backend/executor/blast_result', methods=['POST'])
def blast_result():
    """获取BLAST结果"""
    data = request.get_json(force=True)
    task_id = data.get('id', '').strip()
    
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return "NULL"
        
        if task.state == 'DONE' and hasattr(task, 'results') and task.results:
            return task.results
        elif task.state == 'ERROR':
            return "ERROR"
        elif task.state == 'WORKING':
            return "WORKING"
        else:
            return "NULL"


@app.route('/backend/executor/vdj_submit', methods=['POST'])
def vdj_submit():
    """提交VDJ分析（兼容接口，暂不实现）"""
    task_id = str(uuid.uuid4())[:12]
    return task_id


@app.route('/backend/executor/vdj_result', methods=['POST'])
def vdj_result():
    """获取VDJ结果（兼容接口，返回空）"""
    return "NULL"


if __name__ == '__main__':
    print("=" * 60)
    print("mRNAviewer Backend Server")
    print("=" * 60)
    print(f"Working directory: {BASE_DIR}")
    print(f"Codon directory: {CODON_DIR}")
    print(f"Workspace directory: {WORKSPACE_DIR}")
    print("=" * 60)
    print("\n🚀 Starting server at http://localhost:5000")
    print("\n📋 Available endpoints:")
    print("  - Frontend: http://localhost:5000/")
    print("  - API: http://localhost:5000/mRNAoptimizer/backend/executor/*")
    print("\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
