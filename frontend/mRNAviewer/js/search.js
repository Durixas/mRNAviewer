var backend_url = "/mRNAviewer" // 后端地址
var common_amino_acid = "ATCGUORNDQEHILKMFPSWYV"
var count = 0;
var handle, image_timer, blast_timer;
var current_work = [];
var tissues = ['general', 'Adrenal_gland', 'Appendix', 'Brain', 'Colon', 'Duodenum', 'Endometrium', 'Esophagus', 'Fallopian_tube', 'Fat', 'Gallbladder', 'Heart', 'Kidney', 'Liver', 'Lung', 'Lymph_node', 'Ovary', 'Pancreas', 'Placenta', 'Prostate', 'Rectum', 'Salivary_gland', 'Small_intestine', 'Smooth_muscle', 'Spleen', 'Stomach', 'Testis', 'Thyroid', 'Tonsil', 'Urinary_bladder']
var query_data = {};
var binding_map_length = 0;

function clear(id) {
    document.getElementById(id).value = '';
    clear_form_error()
    announce("Input sequence cleared.")
}

function paste(id, context) {
    document.getElementById(id).value = context;
    clear_form_error()
    announce("Example sequence loaded into the amino acid input.")
}

function announce(message) {
    document.getElementById("announcements").textContent = message
}

function clear_form_error() {
    var error = document.getElementById("form_error")
    error.hidden = true
    error.textContent = ""
    document.getElementById("Input").removeAttribute("aria-invalid")
    document.getElementById("Input").setAttribute("aria-describedby", "input-instructions")
    document.getElementById("source").removeAttribute("aria-invalid")
    document.getElementById("source").removeAttribute("aria-describedby")
}

function show_form_error(message, fieldId) {
    clear_form_error()
    var error = document.getElementById("form_error")
    error.hidden = false
    error.textContent = message
    var field = document.getElementById(fieldId)
    field.setAttribute("aria-invalid", "true")
    field.setAttribute("aria-describedby", fieldId === "Input" ? "input-instructions form_error" : "form_error")
    field.focus()
}

function clear_range_error() {
    var error = document.getElementById("range_error")
    error.hidden = true
    error.textContent = ""
    document.getElementById("start_index").removeAttribute("aria-invalid")
    document.getElementById("start_index").removeAttribute("aria-describedby")
    document.getElementById("end_index").removeAttribute("aria-invalid")
    document.getElementById("end_index").removeAttribute("aria-describedby")
}

function show_range_error(message) {
    clear_range_error()
    var error = document.getElementById("range_error")
    error.hidden = false
    error.textContent = message
    for (var id of ["start_index", "end_index"]) {
        var field = document.getElementById(id)
        field.setAttribute("aria-invalid", "true")
        field.setAttribute("aria-describedby", "range_error")
    }
    document.getElementById("start_index").focus()
}

function base64_to_blob(text, type_str) {
    var bytes = atob(text)
    var bytesCode = new ArrayBuffer(bytes.length)
    var byteArray = new Uint8Array(bytesCode)
    for (var i = 0; i < bytes.length; ++i) {
        byteArray[i] = bytes.charCodeAt(i);
    }
    return new Blob([bytesCode], { type: type_str })
}

// 加载 存储（实现刷新页面仍能保存之前的查询记录，但关闭页面就无法保存了）
// 先向后端发送一次查询请求,得到后端的数据,再根据这些数据更新前端保留的数据
function load_storage() {
    current_work = []
    var tmp = sessionStorage.getItem("works")
    var backend_data;
    if (tmp != null) {
        tmp = JSON.parse(tmp)  // change string to object
        sessionStorage.clear()

        // 先向后端请求一次数据,用来判断是否有数据过期失效
        $.ajax({
            type: "post",
            url: backend_url + "/backend/executor/queueing",
            async: false,
            success: function (data) {
                // data 包含所有任务的 id 和 state
                backend_data = JSON.parse(data)  // string to javascript
            }
        });

        if (!Array.isArray(backend_data)) {
            sessionStorage.removeItem("works")
            return
        }

        var back_len = backend_data.length

        // 删除已经失效的案例
        for (var i = 0; i < tmp.length; ++i) {
            var j = 0
            for (; j < back_len; ++j) {
                if (tmp[i]['id'] == backend_data[j][0]) {
                    break
                }
            }
            if (j != back_len) {
                tmp[i]["is_show"] = "false"
                // 如果后端返回了tissue信息（backend_data[j][2]），则更新
                if (backend_data[j].length > 2 && backend_data[j][2]) {
                    tmp[i]['tissue'] = backend_data[j][2]  // 直接使用后端返回的tissue名称
                }
                current_work.push(tmp[i])
                // sessionStorage.setItem("works", JSON.stringify(current_work))
            }
        }

        sessionStorage.setItem("works", JSON.stringify(current_work))
        getQueue()
        handle = window.setInterval(getQueue, 2000)
    }
}

// 对输入序列进行简单处理，包括剔除空格，换行，将字符全部变为大写
function input_process(ecode) {
    // 剔除空格
    ecode = ecode.replace(/\ +/g, "")
    // 剔除回车换行符
    ecode = ecode.replace(/[\r\n]/g, "")
    // 小写全部替换为大写
    ecode = ecode.toUpperCase()

    return ecode
}

// Submit 按钮的绑定事件
function onRun() {
    // load_storage()
    clear_form_error()
    var ecode = document.getElementById("Input").value
    var ecode_source = document.getElementById("source").value

    ecode = input_process(ecode)

    // 输入判断
    if (ecode == "") {
        show_form_error("Input sequence is empty, please enter a valid sequence!", "Input")
        return false
    }

    if (ecode_source == "") {
        show_form_error("Please select a tissue type!", "source")
        return false
    }

    // 判断输入是否合法（是否在20中氨基酸之内）
    var legal = "true"
    for (var i = 0; i < ecode.length; ++i) {
        var j = 0;
        for (; j < common_amino_acid.length; ++j) {
            if (ecode[i] == common_amino_acid[j]) {
                break
            }
        }
        if (j == common_amino_acid.length) {
            legal = "false"
            break
        }
    }
    if (legal == "false") {
        show_form_error("Invalid sequence format! Please enter a valid amino acid sequence.", "Input")
        return false
    }

    // 判断输入是否重复
    var con = "true"
    for (var i = 0; i < current_work.length; ++i) {
        if (ecode == current_work[i]['content'] && ecode_source == current_work[i]['tissue']) {
            con = "false"
            break
        }
    }
    if (con == "false") {
        show_form_error("Duplicate submission! This sequence with the same tissue type already exists.", "Input")
        return false
    }

    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/submit",
        data: JSON.stringify({ data: ecode, tissue: ecode_source }),
        async: true,
        success: function (data) {
            var temp = {
                'id': data,
                'content': ecode,
                'tissue': ecode_source,  // ecode_source已经是tissue名称了
                'is_show': "true",
                'state': "Analyzing..."
            }
            current_work.push(temp)
            insert(temp, temp['state'])  // 直接插入到表格中
            announce("Task " + document.getElementById("tbMain").rows.length + " submitted. Analysis is in progress.")
            sessionStorage.setItem("works", JSON.stringify(current_work))
            getQueue()
            handle = setInterval(getQueue, 2000)
        },
        error: function () {
            show_form_error("The task could not be submitted. Please try again.", "Input")
        }
    });
}

// 向后端发送查询，得到所有已提交的实例，并根据实例的状态更新表格和判断是否要停止重复的查询请求
function getQueue() {
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/queueing",
        async: true,
        success: function (data) {
            // data 包含所有任务的 id 和 state
            var arr = JSON.parse(data);  // string to javascript
            console.log("getQueue received:", arr);
            console.log("current_work:", current_work);

            // 找到 current_work 中有的任务
            for (var i = 0; i < current_work.length; ++i) {
                for (var j = 0; j < arr.length; ++j) {
                    // id 相等
                    console.log("Comparing: current_work[" + i + "]['id']=" + current_work[i]['id'] + " vs arr[" + j + "][0]=" + arr[j][0]);
                    if (current_work[i]['id'] == arr[j][0]) {
                        console.log("Match found! Updating state to: " + arr[j][1]);
                        current_work[i]['state'] = arr[j][1]
                        // 如果后端返回了tissue信息（arr[j][2]），则更新或设置
                        if (arr[j].length > 2 && arr[j][2]) {
                            current_work[i]['tissue'] = arr[j][2]  // 直接使用后端返回的tissue名称
                        }
                        if (current_work[i]['is_show'] == "false") {
                            current_work[i]['is_show'] = "true"
                            // 加入到 table 中
                            insert(current_work[i], arr[j][1])
                        }
                        // 更新列表中的状态
                        update_state(current_work[i], i + 1)
                        break
                    }
                }
            }
            if (is_closed()) {
                console.log("All tasks done, stopping queue polling");
                clearInterval(handle)
            }
        }
    });
}

// 判断 getQueue() 是否要结束
function is_closed() {
    for (var i = 0; i < current_work.length; i++) {
        if (current_work[i]['state'] != "Done") {
            return false
        }
    }
    return true
}

function show_empty_works_row() {
    var tbody = document.getElementById("tbMain")
    if (tbody.rows.length > 0) {
        return
    }
    var row = tbody.insertRow()
    row.id = "empty_works_row"
    var cell = row.insertCell()
    cell.colSpan = 5
    cell.setAttribute("headers", "works-id works-sequence works-type works-state works-operate")
    var message = document.createElement("span")
    message.className = "visually-hidden"
    message.textContent = "No analysis tasks yet."
    cell.appendChild(message)
}

// 向表格中插入新的实例
function insert(local_data, query_state) {
    var tbody = document.getElementById("tbMain")
    var emptyRow = document.getElementById("empty_works_row")
    if (emptyRow) {
        emptyRow.remove()
    }

    var new_row = insertDataRow(local_data, query_state,)
    // 这里的 new_row 就是 html 里边的 <tr></tr> 元素之间的所有内容
    tbody.appendChild(new_row)

    // 给新添加的表格行的第一列赋值(改行在表格中的index)
    label_task_row(new_row)
}

function label_task_row(row) {
    var taskNumber = row.rowIndex
    row.cells[0].innerText = taskNumber
    var sequenceButton = row.cells[1].querySelector("button")
    sequenceButton.setAttribute("aria-label", "Copy " + sequenceButton.textContent + " to input for task " + taskNumber)
    row.cells[4].querySelector("input").setAttribute("aria-label", "Select results for task " + taskNumber)
}

// 动态向表格插入数据的具体实现
function insertDataRow(local_data, query_state) {

    var row = document.createElement('tr')  // 创建行
    row.setAttribute("style", "height: 50px; text-align: center;")

    // id
    var idCell = document.createElement('td')  // 创建第一列
    idCell.setAttribute("class", "id")
    row.appendChild(idCell)  // 加入行

    // sequence
    var sequenceCell = document.createElement('td')  // 创建第二列
    var sequenceButton = document.createElement('button')
    sequenceCell.appendChild(sequenceButton)
    sequenceButton.type = "button"
    sequenceButton.className = "sequence-button"
    sequenceButton.onclick = function () { show_all_content(this) }
    sequenceButton.appendChild(document.createTextNode(short_sequence(local_data['content'])))
    row.appendChild(sequenceCell)

    // tissue
    var tissueCell = document.createElement('td')  // 创建第三列
    tissueCell.setAttribute("class", "tissue")
    // 格式化tissue显示：首字母大写，下划线替换为空格
    var tissue = local_data['tissue'] || 'general'
    var displayTissue = tissue.charAt(0).toUpperCase() + tissue.slice(1).replace(/_/g, ' ')
    tissueCell.innerHTML = displayTissue
    row.appendChild(tissueCell)

    // state
    var stateCell = document.createElement('td')  // 创建第四列
    stateCell.setAttribute("class", "state")
    stateCell.innerHTML = query_state
    row.appendChild(stateCell)

    // query
    var queryCell = document.createElement('td')  // 创建第五列
    var query_button = document.createElement('input')
    query_button.setAttribute("type", "button")
    query_button.setAttribute("value", "Select")
    if (query_state != "Done") {
        query_button.setAttribute("style", "background-color: #CCCCCC; cursor: not-allowed;")
        query_button.setAttribute("disabled", "disabled")
    }
    else {
        query_button.setAttribute("style", "background-color: yellow; cursor: pointer;")
        query_button.setAttribute("onclick", "select_query_instance(this)")
    }
    queryCell.appendChild(query_button)
    row.appendChild(queryCell)


    return row  // 返回  tr 数据
}

// 更新表格中每个实例的分析状态
function update_state(data, row_idx) {
    var row = document.getElementById("tbMain").rows[row_idx - 1]
    if (!row) {
        return
    }
    var previousState = row.cells[3].textContent
    row.cells[3].textContent = data['state']
    if (previousState !== data['state']) {
        announce("Task " + row_idx + ": " + data['state'] + (data['state'] === "Done" ? ". Select its results." : "."))
    }
    if (data['state'] == "Done") {
        var button = row.cells[4].querySelector('input')
        button.style.backgroundColor = 'yellow'
        button.style.cursor = 'pointer'
        button.disabled = false
        button.onclick = function () { select_query_instance(this) }
    }
}

// 表格中第二列序列内容的简写
function short_sequence(sequence) {
    var len = sequence.length
    if (len <= 10)
        return sequence
    else {
        subseq_1 = sequence.substring(0, 5)
        subseq_2 = sequence.substring(len - 5, len)
        return subseq_1 + " ... " + subseq_2
    }
}

// 点击序列简写，在输入框显示完整序列
function show_all_content(val) {
    var idx = $(val).parent().parent().children().eq(0).text()  // 第一列的值
    // Find the actual data in current_work array by matching the row index
    var rowIndex = parseInt(idx) - 1;
    if (rowIndex >= 0 && rowIndex < current_work.length) {
        var content = current_work[rowIndex]["content"]
        var inputElement = document.getElementById('Input')
        if (inputElement) {
            inputElement.value = content
            inputElement.focus()
            // Scroll to the input area
            inputElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
    }
}

// 表格中每一行的select按钮功能
function select_query_instance(val) {

    clear_all_existing_data()  // 清除所有数据

    var idx = $(val).parent().parent().children().eq(0).text()  // 第一列的值
    var state = $(val).parent().parent().children().eq(3).text()  // 第四列的值

    var content = current_work[idx - 1]["content"]
    var id = current_work[idx - 1]["id"]

    document.getElementById('Input').value = content

    if (state != "Done") {
        alert("Analysis in progress, please wait!")
        return false
    }
    else {
        // 先清除下边的统计框和选择区间
        clear_existing_data_in_statistics_box()  // 清除已有的数据
        getResult(id, idx)  // 获得后端数据
    }
}

// 设置初始时的 核苷酸数量
function set_original_nucl_cnt() {
    var x = document.getElementById("start_index").value
    var y = document.getElementById("end_index").value
    document.getElementById("nucl_cnt").value = y - x + 1
}

// 获取 id 对应的输入内容
function getContext(id) {
    var ans
    for (var i = 0; i < current_work.length; ++i) {
        if (id == current_work[i]['id']) {
            ans = current_work[i]['content']
            break
        }
    }
    return ans
}

// 把A/T/C/G的统计数据清空
function clear_existing_data_in_statistics_box() {
    // 清空统计区域
    document.getElementById("a_cnt").value = ""
    document.getElementById("a_perc").value = ""
    document.getElementById("t_cnt").value = ""
    document.getElementById("t_perc").value = ""
    document.getElementById("c_cnt").value = ""
    document.getElementById("c_perc").value = ""
    document.getElementById("g_cnt").value = ""
    document.getElementById("g_perc").value = ""
    document.getElementById("nucl_cnt").value = ""
}

// 得到指定输入序列的分析结果（只是序列结果，图片信息在后边）
function getResult(ecode, row_index) {
    var tmain = document.getElementById("tbMain")
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/result",
        data: JSON.stringify({ id: ecode }),
        async: false,
        success: function (data) {
            if (data == "NULL") {
                announce("Task " + row_index + " has expired. Submit a new analysis task.")
                // 删除这一行：
                tmain.deleteRow(row_index - 1)
                // 删除本地 current_work 中存放的数据
                current_work.splice(row_index - 1, 1)
                // 更新列表中的id
                var child = tmain.getElementsByTagName("tr")
                for (var i = 0; i < child.length; ++i) {
                    label_task_row(child[i])
                }
                show_empty_works_row()
                // 隐藏一些组件
                hide_output_interest_stats_picture_table_reset_info()
                document.getElementById("Input").focus()
                return false
            }
            else {
                // Highlight the selected task row.
                var rows = tmain.rows
                for (var i = 0; i < rows.length; ++i) {
                    rows[i].style.backgroundColor = i === row_index - 1 ? "rgb(208, 181, 136)" : "#e9f0f4"
                    if (i === row_index - 1) {
                        rows[i].setAttribute("aria-current", "true")
                    } else {
                        rows[i].removeAttribute("aria-current")
                    }
                }

                // Find the task in current_work by ID (not by row_index)
                console.log("=== DEBUG: Looking for task ===");
                console.log("Task ID (ecode):", ecode);
                console.log("Current work array:", current_work);
                
                var taskIndex = -1;
                for (var i = 0; i < current_work.length; i++) {
                    if (current_work[i]['id'] === ecode) {
                        taskIndex = i;
                        break;
                    }
                }
                
                if (taskIndex === -1) {
                    console.error("Task not found in current_work:", ecode);
                    return false;
                }
                
                console.log("Found task at index:", taskIndex);
                console.log("Task object:", current_work[taskIndex]);

                // Check if we already have cached sequence data for this task
                var taskData;
                if (current_work[taskIndex]['seq_data']) {
                    // Use cached data
                    console.log("✓ Using cached data for task:", ecode);
                    console.log("Cached seq_data:", current_work[taskIndex]['seq_data']);
                    taskData = current_work[taskIndex]['seq_data']
                } else {
                    // Parse new data from backend
                    console.log("✓ Parsing NEW data for task:", ecode);
                    data = $.parseJSON(atob(data))  // change String to JavaScript
                    
                    // Store sequence data in the specific task object
                    taskData = {
                        'full': data["seq"][0],
                        '5utr': data["seq"][1],
                        'orf': data["seq"][2],
                        '3utr': data["seq"][3]
                    }
                    
                    console.log("Storing new seq_data:", taskData);
                    // Save to current_work for this specific task
                    current_work[taskIndex]['seq_data'] = taskData
                    sessionStorage.setItem("works", JSON.stringify(current_work))
                }
                
                // Update global query_data for display
                query_data['full'] = taskData['full']
                query_data['5utr'] = taskData['5utr']
                query_data['orf'] = taskData['orf']
                query_data['3utr'] = taskData['3utr']

                // 实现输出结果的下载：
                download_output_sequence(query_data)

                // Store the current task ID globally so we know which task's data we're working with
                window.currentTaskId = ecode;
                
                clear_stats_alter_and_pic()  // 如果在上一次选择的基础上重现选择新的query instance，那么还要隐藏 统计区域和图片区域
                clear_existing_data_in_full_seq_and_interest_area()  // 清除组件中已有的信息
                show_full_seq_and_interest_region()  // 显示组件
                add_data_to_full_seq()  // 向组件中添加新信息
                init_slider()  // 初始化滑块

                // 为 interest_region中的 start、end、nuclectides设置初始值
                set_full_region()  // 设置 [start, end] 为序列的全部长度
                set_original_nucl_cnt()  // 计算 [start, end]之间有多少核苷酸
                document.getElementById("output_rna_seq").focus()
                announce("Results for task " + row_index + " are displayed. Use the range controls to explore the sequence.")
            }
        }
    });
}

function download_output_sequence(data) {
    var output = "Sequence type\tSequence\n" +
        "Full\t" + data['full'] + "\n" +
        "5' UTR\t" + data['5utr'] + "\n" +
        "ORF\t" + data['orf'] + "\n" +
        "3' UTR\t" + data['3utr'] + "\n"
    set_download_text("full_seq_file", "Output_Sequence.txt", output)
}

// 仅展示 full_seq和感兴趣区域
function show_full_seq_and_interest_region() {
    var obj1 = document.getElementById("output_rna_seq")
    if (obj1.style.display == "none") {
        obj1.style.display = ""
    }

    var obj2 = document.getElementById("interest_region")
    if (obj2.style.display == "none") {
        obj2.style.display = ""
    }

    var obj3 = document.getElementById("tips")
    if (obj3.style.display == "none") {
        obj3.style.display = ""
    }
}

// 清除 full_seq和感兴趣区域 已有的数据
function clear_existing_data_in_full_seq_and_interest_area() {
    $("#full_info").empty()
    $("#mytxt").empty()
}

// 向full_seq 区域添加新的信息
function add_data_to_full_seq() {
    show_full_info()  // 设置头
    show_full_sequence_with_different_color()  // 将全序列设置为不同颜色
    show_output_rna()  // 显示全部序列（供滑块滑动的那个长条）
}

function show_full_info() {
    var len1 = query_data["5utr"].length
    var len2 = query_data["orf"].length
    var len3 = query_data["3utr"].length
    var a_2 = len1 + 1
    var b_2 = len1 + len2
    var a_3 = b_2 + 1
    var b_3 = len1 + len2 + len3
    var info_div = document.getElementById("full_info")

    var head_span = document.createElement("span")
    info_div.appendChild(head_span)
    head_span.setAttribute("style", "font-weight: bold")
    head_span.innerText = "Output Sequence: "

    var utr5_simple_info = document.createElement("span")
    info_div.appendChild(utr5_simple_info)
    utr5_simple_info.setAttribute("style", "color: blue")
    utr5_simple_info.innerText = " 5′ UTR (1-" + len1 + "),"

    var orf_simple_info = document.createElement("span")
    info_div.appendChild(orf_simple_info)
    orf_simple_info.setAttribute("style", "color: #642e16")
    orf_simple_info.innerText = " ORF (" + a_2 + "-" + b_2 + "),"

    var utr3_simple_info = document.createElement("span")
    info_div.appendChild(utr3_simple_info)
    utr3_simple_info.setAttribute("style", "color: green")
    utr3_simple_info.innerText = " 3′ UTR (" + a_3 + "-" + b_3 + "), "

    var choose = document.createElement("span")
    info_div.appendChild(choose)
    choose.setAttribute("style", "background-color: silver")
    choose.innerText = "gray fonts"

    var tag = document.createElement("span")
    info_div.appendChild(tag)
    tag.innerText = " (" + "the sequence that has been selected" + ")"
}

function original_colorful_full_seq() {
    var full_txt = query_data['full']

    let str1 = full_txt.replace(query_data['5utr'], function (v) {
        return v.fontcolor("blue")
    })

    let str2 = str1.replace(query_data['orf'], function (v) {
        return v.fontcolor("orange")
    })

    let str3 = str2.replace(query_data['3utr'], function (v) {
        return v.fontcolor("green")
    })

    return str3
}

function show_full_sequence_with_different_color() {
    var txt_div = document.getElementById("mytxt")
    txt_div.innerHTML = original_colorful_full_seq()
}

function clear_stats_alter_and_pic() {
    var obj = document.getElementById("stats_res")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("alter")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("pic_section")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("table_info")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("reset_button")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }
}

function show_output_rna() {
    var full_len = query_data['full'].length
    var utr5_len = query_data['5utr'].length
    var orf_len = query_data['orf'].length

    var a = 100 * utr5_len / full_len
    var b = 100 * orf_len / full_len
    var c = 100 - a - b

    var width_utr5 = document.getElementById("subseq_utr5")
    var width_orf = document.getElementById("subseq_orf")
    var width_utr3 = document.getElementById("subseq_utr3")

    width_utr5.style.width = a.toString() + "%"
    width_orf.style.width = b.toString() + "%"
    width_utr3.style.width = c.toString() + "%"
}

// Highlight the active region button
function highlight_active_region_button(activeId) {
    // Remove active class from all buttons
    var buttons = ['full_btn', 'utr5_btn', 'orf_btn', 'utr3_btn']
    buttons.forEach(function(btnId) {
        var btn = document.getElementById(btnId)
        if (btn) {
            btn.setAttribute("aria-pressed", btnId === activeId ? "true" : "false")
            if (btnId === activeId) {
                btn.style.backgroundColor = '#d4a574'
                btn.style.color = '#002856'
                btn.style.fontWeight = 'bold'
                btn.style.border = '2px solid #8b6f47'
            } else {
                btn.style.backgroundColor = '#f0f0f0'
                btn.style.color = '#666'
                btn.style.fontWeight = 'normal'
                btn.style.border = '1px solid #ccc'
            }
        }
    })
}

function set_full_region() {
    clear_range_error()
    var leen = query_data['full'].length
    document.getElementById("start_index").start_value = 1
    document.getElementById("end_index").end_value = leen
    update_slider_position()
    show_current_subseq_with_red()
    highlight_active_region_button('full_btn')
}

function set_utr5_region() {
    clear_range_error()
    var leen = query_data['5utr'].length
    document.getElementById("start_index").start_value = 1
    document.getElementById("end_index").end_value = leen
    update_slider_position()
    show_current_subseq_with_red()
    highlight_active_region_button('utr5_btn')
}

function set_orf_region() {
    clear_range_error()
    var leen = query_data['5utr'].length
    var leen2 = query_data['orf'].length
    document.getElementById("start_index").start_value = leen + 1
    document.getElementById("end_index").end_value = leen + leen2
    update_slider_position()
    show_current_subseq_with_red()
    highlight_active_region_button('orf_btn')
}

function set_utr3_region() {
    clear_range_error()
    var leen = query_data['full'].length
    var leen2 = query_data['3utr'].length
    document.getElementById("start_index").start_value = leen - leen2 + 1
    document.getElementById("end_index").end_value = leen
    update_slider_position()
    show_current_subseq_with_red()
    highlight_active_region_button('utr3_btn')
}

// 得到选中的 核苷酸序列
function get_text_queried() {
    var start_index = Number(document.getElementById('start_index').value)
    var end_index = Number(document.getElementById('end_index').value)
    var len_of_full = query_data['full'].length
    var gap_1 = query_data['5utr'].length
    var gap_2 = query_data['5utr'].length + query_data['orf'].length

    // start_index 和 end_index 是 string，要转为 int 再比较
    if (start_index <= 0 || start_index >= end_index || end_index > len_of_full) {
        show_range_error("Invalid range. Start must be greater than 0 and End must be greater than Start without exceeding " + len_of_full + ".")
        return false
    }
    else {
        let full_queried_seq = query_data['full'].substring(start_index - 1, end_index)
        let query_seq_in_5utr = ""
        let query_seq_in_orf = ""
        let query_seq_in_3utr = ""

        if (start_index <= gap_1) {
            // 说明开始在 5utr里
            if (end_index <= gap_1) {
                // 整个在 5utr 里
                query_seq_in_5utr = full_queried_seq
                l1 = start_index
                r1 = end_index
                l2 = 0
                r2 = 0
                l3 = 0
                r3 = 0
            }
            else if (end_index <= gap_2) {
                // 在 5utr 和 orf 里
                query_seq_in_5utr = query_data['full'].substring(start_index - 1, gap_1)
                query_seq_in_orf = query_data['full'].substring(gap_1, end_index + 1)
                l1 = start_index
                r1 = gap_1
                l2 = gap_1 + 1
                r2 = end_index
                l3 = 0
                r3 = 0
            }
            else {
                // 三部分都有
                query_seq_in_5utr = query_data['full'].substring(start_index - 1, gap_1)
                query_seq_in_orf = query_data['full'].substring(gap_1, gap_2)
                query_seq_in_3utr = query_data['full'].substring(gap_2, end_index)
                l1 = start_index
                r1 = gap_1
                l2 = gap_1 + 1
                r2 = gap_2 - 1
                l3 = gap_2
                r3 = end_index
            }
        }
        else if (start_index <= gap_2) {
            // 说明起始在 orf 里
            if (end_index <= gap_2) {
                // 只在 orf 里
                query_seq_in_orf = full_queried_seq
                l1 = 0
                r1 = 0
                l2 = start_index
                r2 = end_index
                l3 = 0
                r3 = 0
            }
            else {
                // 起始在 orf 里，结束在 3utr 里
                query_seq_in_orf = query_data['full'].substring(start_index - 1, gap_2)
                query_seq_in_3utr = query_data['full'].substring(gap_2, end_index)
                l1 = 0
                r1 = 0
                l2 = start_index
                r2 = gap_2 - 1
                l3 = gap_2
                r3 = end_index
            }
        }
        else {
            // 全都在 3utr 里
            query_seq_in_3utr = full_queried_seq
            l1 = 0
            r1 = 0
            l2 = 0
            r2 = 0
            l3 = start_index
            r3 = end_index
        }

        return [full_queried_seq, query_seq_in_5utr, query_seq_in_orf, query_seq_in_3utr, l1, r1, l2, r2, l3, r3]
    }
}

// 用红色字体显示被选中的文本
function show_current_subseq_with_red() {

    // <font color="blue"> 的长度为 19
    // </font><font color="orangered"> 的长度为 31
    // </font><font color="green"> 的长度为 27
    // </font> 的长度为 7
    let len_1 = 19, len_2 = 28, len_3 = 27

    let full_seq = original_colorful_full_seq()

    let seq = get_text_queried()
    if (seq === false) {
        return
    }

    let l1 = seq[4], r1 = seq[5], l2 = seq[6], r2 = seq[7], l3 = seq[8], r3 = seq[9]

    l1 = l1 + len_1
    r1 = r1 + len_1
    l2 = l2 + len_1 + len_2
    r2 = r2 + len_1 + len_2
    l3 = l3 + len_1 + len_2 + len_3
    r3 = r3 + len_1 + len_2 + len_3

    if (seq[1] != "" && seq[2] != "" && seq[3] != "") {
        // 占 3 部分
        let a = full_seq.split("")
        a.splice(r3, 0, '</p>')
        a.splice(l1 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }
    else if (seq[1] != "" && seq[2] != "" && seq[3] == "") {
        // 在 5utr 和 orf
        let a = full_seq.split("")
        a.splice(r2, 0, '</p>')
        a.splice(l1 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }
    else if (seq[1] == "" && seq[2] != "" && seq[3] != "") {
        // 在 orf 和 3utr
        let a = full_seq.split("")
        a.splice(r3, 0, '</p>')
        a.splice(l2 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }
    else if (seq[1] != "" && seq[2] == "" && seq[3] == "") {
        // 只在 5utr
        let a = full_seq.split("")
        a.splice(r1, 0, '</p>')
        a.splice(l1 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }
    else if (seq[1] == "" && seq[2] != "" && seq[3] == "") {
        // 只在 orf
        let a = full_seq.split("")
        a.splice(r2, 0, '</p>')
        a.splice(l2 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }
    else if (seq[1] == "" && seq[2] == "" && seq[3] != "") {
        // 只在 3utr
        let a = full_seq.split("")
        a.splice(r3, 0, '</p>')
        a.splice(l3 - 1, 0, '<p style="display: inline; background-color: silver">')
        full_seq = a.join("")
    }

    document.getElementById("mytxt").innerHTML = full_seq
}


function update_slider_accessibility(values) {
    var max = query_data['full'].length
    $("#slider-range .ui-slider-handle").each(function (index) {
        this.removeAttribute("href")
        this.setAttribute("role", "slider")
        this.setAttribute("tabindex", "0")
        this.setAttribute("aria-label", index === 0 ? "Start position" : "End position")
        this.setAttribute("aria-orientation", "horizontal")
        this.setAttribute("aria-valuemin", "1")
        this.setAttribute("aria-valuemax", String(max))
        this.setAttribute("aria-valuenow", String(values[index]))
        this.setAttribute("aria-controls", index === 0 ? "start_index" : "end_index")
    })
}

function sync_slider_selection(values) {
    $("#start_index").val(values[0])
    $("#end_index").val(values[1])
    $("#nucl_cnt").val(values[1] - values[0] + 1)
    update_slider_accessibility(values)
}

function finish_slider_selection() {
    clear_table_info()
    highlight_active_region_button(null)
    show_current_subseq_with_red()
    update_slider_accessibility($("#slider-range").slider('values'))
}

function install_touch_slider() {
    var slider = document.getElementById("slider-range")
    if (!slider || slider.dataset.touchSliderInstalled) return
    slider.dataset.touchSliderInstalled = "true"

    var activePointer = null
    var activeHandle = null
    var selectionChanged = false

    function value_at_pointer(clientX) {
        var rect = slider.getBoundingClientRect()
        var fraction = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
        return 1 + Math.round(fraction * (query_data['full'].length - 1))
    }

    function move_handle(clientX) {
        var values = $(slider).slider('values')
        var value = value_at_pointer(clientX)
        value = activeHandle === 0 ? Math.min(value, values[1]) : Math.max(value, values[0])
        if (value === values[activeHandle]) return
        $(slider).slider('values', activeHandle, value)
        sync_slider_selection($(slider).slider('values'))
        selectionChanged = true
    }

    slider.addEventListener('pointerdown', function (event) {
        if ((event.pointerType !== 'touch' && event.pointerType !== 'pen') || activePointer !== null || !event.isPrimary) return
        var handles = slider.querySelectorAll('.ui-slider-handle')
        var targetHandle = event.target.closest('.ui-slider-handle')
        if (targetHandle === handles[0]) activeHandle = 0
        else if (targetHandle === handles[1]) activeHandle = 1
        else {
            var values = $(slider).slider('values')
            var value = value_at_pointer(event.clientX)
            activeHandle = Math.abs(value - values[0]) <= Math.abs(value - values[1]) ? 0 : 1
        }
        activePointer = event.pointerId
        selectionChanged = false
        slider.setPointerCapture(event.pointerId)
        event.preventDefault()
        if (!targetHandle) move_handle(event.clientX)
    })

    slider.addEventListener('pointermove', function (event) {
        if (event.pointerId !== activePointer) return
        event.preventDefault()
        move_handle(event.clientX)
    })

    function stop_touch_drag(event) {
        if (event.pointerId !== activePointer) return
        event.preventDefault()
        activePointer = null
        activeHandle = null
        if (selectionChanged) finish_slider_selection()
    }

    slider.addEventListener('pointerup', stop_touch_drag)
    slider.addEventListener('pointercancel', stop_touch_drag)
}

function init_slider() {
    var sliderTimeout = null;
    
    $("#slider-range").slider({
        range: true,
        min: 1,
        max: query_data['full'].length,
        values: [1, query_data['full'].length],
        slide: function (event, ui) {
            sync_slider_selection(ui.values)
        }
    });
    update_slider_accessibility([1, query_data['full'].length])
    install_touch_slider()

    // 在于滑块交互结束时的绑定事件
    $("#slider-range").off('slidestop').on('slidestop', function (event, ui) {
        console.log("滑块停止，等待用户点击确定按钮")
        finish_slider_selection()
    })
}

// 更新滑块位置以匹配当前选择的start和end
function update_slider_position() {
    var start_index = Number(document.getElementById('start_index').value)
    var end_index = Number(document.getElementById('end_index').value)
    if (start_index && end_index) {
        $("#slider-range").slider('values', [start_index, end_index])
        update_slider_accessibility([start_index, end_index])
    }
}

function set_nucl_cnt() {
    console.log("count++")
    if (++count == 2) {
        console.log("触发！！！")
        var x = document.getElementById("start_index").value
        var y = document.getElementById("end_index").value
        document.getElementById("nucl_cnt").value = y - x + 1
        get_stats_picture_and_table_data()
        count = 0
    }
}

// 获得子序列更多信息（统计信息、图片、表格）
function get_stats_picture_and_table_data() {
    // // 清除之前的轮询定时器，避免并发冲突
    // if (image_timer) {
    //     clearInterval(image_timer);
    //     console.log("清除之前的 image_timer");
    // }
    // if (blast_timer) {
    //     clearInterval(blast_timer);
    //     console.log("清除之前的 blast_timer");
    // }
    
    // 先得到要查询的子序列序列
    var selected = get_text_queried()
    if (selected !== false) {
        var text = selected[0]
        // 向组件中添加信息
        announce("Analyzing the selected sequence region.")
        calculate(text)  // 统计信息
        genenate_image(text)  // 图片
        blast_submit(text)  // blast

        // 显示组件
        show_stats_picture_and_table_info()
    }
}

// 计算选择多少核苷酸和统计信息（内无其他方法）
function calculate(text) {
    var len = text.length
    var counts = new Array(0, 0, 0, 0)
    for (var i = 0; i < len; ++i) {
        if (text[i] == "A") { counts[0]++ }
        if (text[i] == "T") { counts[1]++ }
        if (text[i] == "C") { counts[2]++ }
        if (text[i] == "G") { counts[3]++ }
    }
    // show count
    document.getElementById('a_cnt').value = counts[0]
    document.getElementById('t_cnt').value = counts[1]
    document.getElementById('c_cnt').value = counts[2]
    document.getElementById('g_cnt').value = counts[3]

    // show percentage
    document.getElementById("a_perc").value = (counts[0] / text.length * 100).toFixed(2) + "%"
    document.getElementById("t_perc").value = (counts[1] / text.length * 100).toFixed(2) + "%"
    document.getElementById("c_perc").value = (counts[2] / text.length * 100).toFixed(2) + "%"
    document.getElementById("g_perc").value = (counts[3] / text.length * 100).toFixed(2) + "%"

}

// 根据 text 的序列生成对应的二级结构并显示
function genenate_image(text) {
    var sub_sequence_id
    // var difer = $.Diferred()
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/gen_image",
        data: JSON.stringify({ data: text }),
        async: false,  // 不能是 异步
        success: function (data) {
            // data 就是序列 id
            sub_sequence_id = data
        }
    });

    // 先杀死所有定时器
    if (image_timer) {
        clearInterval(image_timer)
    }
    image_timer = setInterval(get_mfe, 2000, sub_sequence_id);

}

// 查询mfe
function get_mfe(seq_id) {
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/get_mfe",
        data: JSON.stringify({ id: $.trim(seq_id) }),
        async: true,
        success: function (data) {
            if (data == "WORKING" || data == "NULL") {
                // console.log(image_timer)
            }
            else {
                clearInterval(image_timer)
                obj = document.getElementById("alter")
                if (obj.style.display == "") {
                    obj.style.display = "none"
                }

                obj = document.getElementById("pic_section")
                if (obj.style.display == "none") {
                    obj.style.display = ""
                }

                obj = document.getElementById("table_info")
                if (obj.style.display == "none") {
                    obj.style.display = ""
                }

                obj = document.getElementById("reset_button")
                if (obj.style.display == "none") {
                    obj.style.display = ""
                }

                document.getElementById("mfe").value = data + "kcal/mol"
                document.getElementById("second_structure").alt = "Predicted RNA secondary structure for the selected " + document.getElementById("nucl_cnt").value + " nucleotide sequence; minimum free energy " + data + " kilocalories per mole."
                get_img(seq_id)
                announce("Minimum free energy is " + data + " kilocalories per mole.")
            }
        }
    });
}

// 查询 二级结构图片
function get_img(seq_id) {
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/get_image",
        data: JSON.stringify({ id: $.trim(seq_id) }),
        async: true,
        success: function (data) {
            if (!data || data === "NULL") {
                announce("Secondary structure image is unavailable.")
                return
            }
            $("#second_structure").attr('src', "data:image/png;base64," + data)
            announce("Secondary structure image is available.")
        }
    });
}


function show_stats_picture_and_table_info() {
    var obj = document.getElementById("stats_res")
    if (obj.style.display == "none") {
        obj.style.display = ""
    }

    obj = document.getElementById("alter")
    if (obj.style.display == "none") {
        obj.style.display = ""
    }

    obj = document.getElementById("table_info")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("pic_section")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("reset_button")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }
}

function hide_output_interest_stats_picture_table_reset_info() {
    var selectedButton = document.querySelector('#tbMain tr[aria-current="true"] input')
    var focusedInResults = ["output_rna_seq", "interest_region", "stats_res", "pic_section", "table_info", "reset_button"].some(function (id) {
        return document.getElementById(id).contains(document.activeElement)
    })
    Array.from(document.getElementById("tbMain").rows).forEach(function (row) {
        row.removeAttribute("aria-current")
        row.style.backgroundColor = "#e9f0f4"
    })
    obj = document.getElementById("stats_res")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("pic_section")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("table_info")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("reset_button")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("output_rna_seq")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }

    obj = document.getElementById("interest_region")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }
    obj = document.getElementById("tips")
    if (obj.style.display == "") {
        obj.style.display = "none"
    }
    if (focusedInResults) {
        (selectedButton || document.getElementById("Input")).focus()
    }
}

// 提交 balst 分析
function blast_submit(text) {
    binding_map_length = text.length
    clear_table_info("Searching...")
    $("#binding_error").text("")
    var blast_id
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/blast_submit",
        data: JSON.stringify({ data: text }),
        async: false,  // 不能是 异步
        success: function (data) {
            // data 就是序列 id
            blast_id = data
        }
    });

    // 先杀死所有定时器
    if (blast_timer) {
        clearInterval(blast_timer)
    }
    blast_timer = setInterval(blast_result, 2000, blast_id);
}

function blast_result(blast_id) {
    $.ajax({
        type: "post",
        url: backend_url + "/backend/executor/blast_result",
        data: JSON.stringify({ id: $.trim(blast_id) }),
        async: true,
        success: function (data) {
            if (data == "NULL" || data === "WORKING") {
                // console.log(blast_timer)
            }
            else if (data === "ERROR") {
                clearInterval(blast_timer)
                clear_table_info("Results unavailable.")
                $("#binding_error").text("Binding-site analysis failed. Please try again or contact the site administrator.")
            }
            else {
                clearInterval(blast_timer)
                // 返回的 data 的类型是 string，形式为: ["123","456","789"] 

                data = JSON.parse(data)
                set_download_link(data[0], data[1], data[2], data[3], data[4])

                var harpinCount = harpin_info(data[0], data[3])
                var matureCount = mature_info(data[1], data[4])
                var rbpCount = rbpdb_info(data[2], data[5])
                render_binding_map(data)
                announce("Binding-site analysis complete: " + harpinCount + " stem-loop, " + matureCount + " mature miRNA, and " + rbpCount + " RBP matches.")
            }
        }
    });
}

// 设置最下边的文件的下载
function set_download_text(id, filename, content) {
    var link = document.getElementById(id)
    if (link.dataset.downloadUrl) {
        window.URL.revokeObjectURL(link.dataset.downloadUrl)
    }
    var url = window.URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }))
    link.href = url
    link.download = filename
    link.dataset.downloadUrl = url
}

function binding_lines(encoded) {
    var content = atob(encoded || "").replace(/\r/g, "")
    return content ? content.split("\n").filter(function (line) { return line.trim() !== "" }) : []
}

function format_mirna_download(matches, accessions) {
    var rows = binding_lines(matches)
    var ids = binding_lines(accessions)
    var content = "Accession\tSubject ID\tIdentity\tAlignment length\tMismatches\tGap openings\tQuery start\tQuery end\tSubject start\tSubject end\tE-value\tBit score\n"
    for (var i = 0; i < rows.length; i++) {
        var columns = rows[i].split("\t")
        if (columns.length === 12 && ids[i]) {
            content += ids[i] + "\t" + columns.slice(1).join("\t") + "\n"
        }
    }
    return content
}

function set_download_link(hairpin, mature, rbp, hairpinAcc, matureAcc) {
    set_download_text("blast_hairpin_file", "Stem_loop.txt", format_mirna_download(hairpin, hairpinAcc))
    set_download_text("blast_mature_file", "Mature.txt", format_mirna_download(mature, matureAcc))
    var rows = binding_lines(rbp)
    set_download_text("blast_table_file", "RBP.txt", "RBP name,Start,End,Matching sequence\n" + (rows.length ? rows.join("\n") + "\n" : ""))
}

function binding_map_site(start, end, length, name) {
    start = Number(start)
    end = Number(end)
    if (!Number.isInteger(start) || !Number.isInteger(end)) return null
    var first = Math.min(start, end)
    var last = Math.max(start, end)
    if (first < 1 || last > length) return null
    return { start: first, end: last, name: name }
}

function mirna_map_sites(encoded, length) {
    return binding_lines(encoded).map(function (line) {
        var columns = line.split("\t")
        if (!columns[1] || columns[1].indexOf("hsa-") !== 0) return null
        return binding_map_site(columns[6], columns[7], length, columns[1])
    }).filter(Boolean)
}

function rbp_map_sites(encoded, length) {
    return binding_lines(encoded).map(function (line) {
        var columns = parse_rbp_row(line)
        return binding_map_site(columns[1], columns[2], length, columns[0])
    }).filter(Boolean)
}

function render_binding_map_lane(parent, label, color, sites, length) {
    var row = document.createElement("div")
    row.className = "binding-map-row"
    var caption = document.createElement("span")
    caption.className = "binding-map-label"
    caption.textContent = label + " (" + sites.length + ")"
    row.appendChild(caption)

    var track = document.createElement("div")
    track.className = "binding-map-track"
    track.style.setProperty("--map-color", color)
    track.setAttribute("role", "img")
    track.setAttribute("aria-label", label + ": " + sites.length + " sites across " + length + " nucleotides")
    if (sites.length === 0) {
        var empty = document.createElement("span")
        empty.className = "visually-hidden"
        empty.textContent = "No sites"
        track.appendChild(empty)
    } else if (sites.length <= 150) {
        sites.forEach(function (site) {
            var mark = document.createElement("span")
            mark.className = "binding-map-site"
            mark.style.left = ((site.start - 1) * 100 / length) + "%"
            mark.style.width = ((site.end - site.start + 1) * 100 / length) + "%"
            mark.title = site.name + ": " + site.start + "–" + site.end
            track.appendChild(mark)
        })
    } else {
        var binCount = Math.min(80, length)
        var counts = Array(binCount).fill(0)
        sites.forEach(function (site) {
            var first = Math.floor((site.start - 1) * binCount / length)
            var last = Math.min(binCount - 1, Math.floor((site.end - 1) * binCount / length))
            for (var index = first; index <= last; index++) counts[index]++
        })
        var maximum = Math.max.apply(null, counts)
        counts.forEach(function (count, index) {
            if (!count) return
            var mark = document.createElement("span")
            mark.className = "binding-map-density"
            mark.style.left = (index * 100 / binCount) + "%"
            mark.style.width = (100 / binCount) + "%"
            mark.style.height = (4 + 20 * count / maximum) + "px"
            var first = Math.floor(index * length / binCount) + 1
            var last = Math.ceil((index + 1) * length / binCount)
            mark.title = count + " sites: " + first + "–" + last
            track.appendChild(mark)
        })
    }
    row.appendChild(track)
    parent.appendChild(row)
}

function render_binding_map(data) {
    var section = document.getElementById("binding_site_map")
    var length = binding_map_length || Number(document.getElementById("nucl_cnt").value)
    var lanes = document.getElementById("binding_map_lanes")
    lanes.textContent = ""
    section.hidden = true
    if (!Number.isInteger(length) || length < 1) return

    var groups = [
        { label: "Stem-loop miRNA", color: "#005f91", sites: mirna_map_sites(data[0], length) },
        { label: "Mature miRNA", color: "#a04b13", sites: mirna_map_sites(data[1], length) },
        { label: "RBP", color: "#23683a", sites: rbp_map_sites(data[2], length) }
    ]
    if (!groups.some(function (group) { return group.sites.length > 0 })) return

    var ticks = document.getElementById("binding_map_ticks")
    ticks.textContent = ""
    ;[1, Math.ceil(length / 2), length].forEach(function (position) {
        var tick = document.createElement("span")
        tick.textContent = position
        ticks.appendChild(tick)
    })
    groups.forEach(function (group) {
        render_binding_map_lane(lanes, group.label, group.color, group.sites, length)
    })
    section.hidden = false
}

function set_binding_rows(tableId, rows, emptyMessage) {
    var body = document.getElementById(tableId + "_main")
    var headers = document.querySelectorAll("#" + tableId + " thead th")
    var tableName = { harpin: "Stem-loop miRNA", mature: "Mature miRNA", rbpdb: "RBP" }[tableId]
    var controls = document.getElementById(tableId + "_pagination")
    var buttons = controls.querySelectorAll("button")
    var select = controls.querySelector("select")
    var totalPages = Math.max(1, Math.ceil(rows.length / 20))
    var page = 1

    select.textContent = ""
    for (var i = 1; i <= totalPages; i++) {
        var option = document.createElement("option")
        option.value = i
        option.textContent = i
        select.appendChild(option)
    }
    controls.hidden = totalPages <= 1
    controls.querySelector(".page-total").textContent = "/ " + totalPages

    function render() {
        body.textContent = ""
        if (rows.length === 0) {
            var row = body.insertRow()
            row.className = "binding-empty"
            var cell = row.insertCell()
            cell.colSpan = headers.length
            var headerIds = []
            for (var column = 0; column < headers.length; column++) {
                headers[column].id = tableId + "-column-" + column
                headers[column].setAttribute("scope", "col")
                headerIds.push(headers[column].id)
            }
            cell.setAttribute("headers", headerIds.join(" "))
            cell.textContent = emptyMessage || "No matches found."
        }
        var first = (page - 1) * 20
        for (var i = first; i < Math.min(first + 20, rows.length); i++) {
            body.appendChild(rows[i])
        }
        select.value = page
        buttons[0].disabled = page === 1
        buttons[1].disabled = page === totalPages
    }
    buttons[0].onclick = function () {
        if (page > 1) {
            page--
            render()
            announce(tableName + " page " + page + " of " + totalPages + ".")
        }
    }
    buttons[1].onclick = function () {
        if (page < totalPages) {
            page++
            render()
            announce(tableName + " page " + page + " of " + totalPages + ".")
        }
    }
    select.onchange = function () {
        page = Number(select.value)
        render()
        announce(tableName + " page " + page + " of " + totalPages + ".")
    }
    render()
}

function mirbase_url(accession) {
    if (/^MIMAT\d{7}$/.test(accession)) {
        return "https://mirbase.org/mature/" + accession
    }
    if (/^MI\d{7}$/.test(accession)) {
        return "https://mirbase.org/hairpin/" + accession
    }
    return null
}

function append_link_or_text(cell, label, url) {
    if (url) {
        var link = document.createElement("a")
        link.href = url
        link.target = "_blank"
        link.rel = "noopener noreferrer"
        link.style.color = "blue"
        link.style.textDecoration = "underline"
        link.textContent = label
        cell.appendChild(link)
    } else {
        cell.textContent = label
    }
}

function add_row_to_mature(row, accession) {
    var columns = row.split("\t")
    var result = document.createElement("tr")
    result.style.height = "40px"
    result.style.textAlign = "center"
    var url = mirbase_url(accession)
    var accessionCell = document.createElement("td")
    append_link_or_text(accessionCell, accession || columns[1], url)
    result.appendChild(accessionCell)
    for (var i = 1; i < columns.length; i++) {
        var cell = document.createElement("td")
        if (i === 1) {
            append_link_or_text(cell, columns[i], url)
        } else {
            cell.textContent = columns[i]
        }
        result.appendChild(cell)
    }
    return result
}

function harpin_info(data, accessions) {
    var rows = binding_lines(data)
    var ids = binding_lines(accessions)
    var result = []
    for (var i = 0; i < rows.length; i++) {
        var columns = rows[i].split("\t")
        if (columns[1] && columns[1].indexOf("hsa-") === 0) {
            result.push(add_row_to_mature(rows[i], ids[i]))
        }
    }
    set_binding_rows("harpin", result)
    return result.length
}

function mature_info(data, accessions) {
    var rows = binding_lines(data)
    var ids = binding_lines(accessions)
    var result = []
    for (var i = 0; i < rows.length; i++) {
        var columns = rows[i].split("\t")
        if (columns[1] && columns[1].indexOf("hsa-") === 0) {
            result.push(add_row_to_mature(rows[i], ids[i]))
        }
    }
    set_binding_rows("mature", result)
    return result.length
}

function parse_rbp_row(row) {
    var columns = []
    var value = ""
    var quoted = false
    for (var i = 0; i < row.length; i++) {
        var character = row[i]
        if (character === '"') {
            if (quoted && row[i + 1] === '"') {
                value += '"'
                i++
            } else {
                quoted = !quoted
            }
        } else if (character === "," && !quoted) {
            columns.push(value)
            value = ""
        } else {
            value += character
        }
    }
    columns.push(value)
    return columns
}

function add_row_to_rbpdb(row, geneId) {
    var columns = parse_rbp_row(row)
    var result = document.createElement("tr")
    result.style.height = "40px"
    result.style.textAlign = "center"
    var cell = document.createElement("td")
    var url = /^ENSG\d+$/.test(geneId)
        ? "https://www.ensembl.org/id/" + geneId
        : "https://www.ensembl.org/Multi/Search/Results?q=" + encodeURIComponent(columns[0])
    append_link_or_text(cell, columns[0], url)
    result.appendChild(cell)
    for (var i = 1; i < columns.length; i++) {
        cell = document.createElement("td")
        cell.textContent = columns[i]
        result.appendChild(cell)
    }
    return result
}

function rbpdb_info(data, hyperlinks) {
    var rows = binding_lines(data)
    var ids = binding_lines(hyperlinks)
    var result = []
    for (var i = 0; i < rows.length; i++) {
        result.push(add_row_to_rbpdb(rows[i], ids[i] || ""))
    }
    set_binding_rows("rbpdb", result)
    return result.length
}

// 选取子片段时，清空表格内的数据
function clear_table_info(message) {
    document.getElementById("binding_site_map").hidden = true
    document.getElementById("binding_map_lanes").textContent = ""
    var emptyMessage = message || "No results yet."
    set_binding_rows("harpin", [], emptyMessage)
    set_binding_rows("mature", [], emptyMessage)
    set_binding_rows("rbpdb", [], emptyMessage)
}

// 在选择一个序列时（select按钮），清除所有存在的数据
function clear_all_existing_data() {
    console.log("clear all existing data")
    binding_map_length = 0
    $("#full_info").empty()
    $("#mytxt").empty()

    document.getElementById("a_cnt").value = ""
    document.getElementById("a_perc").value = ""
    document.getElementById("t_cnt").value = ""
    document.getElementById("t_perc").value = ""
    document.getElementById("c_cnt").value = ""
    document.getElementById("c_perc").value = ""
    document.getElementById("g_cnt").value = ""
    document.getElementById("g_perc").value = ""
    document.getElementById("nucl_cnt").value = ""

    clear_table_info()
}
