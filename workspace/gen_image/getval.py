import linecache
import re
text = linecache.getline("fold.log", 3)
num = []
num.append(text)
f = open("./output/mfe.txt",'w+')
f.write(re.findall(r"\-?\d+\.?\d+",num[0])[0])