dir_path = "/mnt/nvme2/chendi/BlueWhale/ai-matrix/macro_benchmark/DIEN_INTEL_TF2/"
file_name = dir_path + "pyspark_data/"
#file_name = dir_path
mid_map = {}

with open(file_name + "local_train_splitByUser", "r") as f_rev:
    row = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[0] == '0':
            if items[2] not in mid_map:
                mid_map[items[2]] = line
        row += 1
        if (row % 100000 == 0):
            print("progress: %d" % row)
print("Total mid count is %d" % len(mid_map))
