dir_path = "/mnt/nvme2/chendi/BlueWhale/ai-matrix/macro_benchmark/DIEN_INTEL_TF2/"
#file_name = dir_path + "pyspark_data/"
file_name = dir_path
fo = open(file_name + "local_train_splitByUser_wo_overlap", "w")
user_map = {}

with open(file_name + "local_test_splitByUser", "r") as f_rev:
    row = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[1] not in user_map:
            user_map[items[1]] = line
        row += 1
        if (row % 10000 == 0):
            print("progress: %d" % row)

with open(file_name + "local_train_splitByUser", "r") as f:
    for line in f.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[1] not in user_map:
            print >> fo, line
