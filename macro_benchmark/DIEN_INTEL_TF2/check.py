dir_path = "/mnt/nvme2/chendi/BlueWhale/ai-matrix/macro_benchmark/DIEN_INTEL_TF2/"
file_name = dir_path + "python_data/"
#file_name = dir_path

with open(file_name + "local_train_splitByUser", "r") as f_rev:
    row = 0
    neg_in_hist_cnt = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        hist_mid = items[4].split('\x02')
        if items[0] == '0' and items[2] in hist_mid:
            neg_in_hist_cnt += 1
            print line
        row += 1
        if (row % 100000 == 0):
            print("Build progress %d" % row)
    print("Found neg in hist cnt as %d" % neg_in_hist_cnt)
