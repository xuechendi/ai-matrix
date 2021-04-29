dir_path = "/mnt/nvme2/chendi/BlueWhale/ai-matrix/macro_benchmark/DIEN_INTEL_TF2/"
file_name = dir_path
fo = open(file_name + "local_train_splitByUser_shuffled", "w")
user_map = {}

with open(file_name + "python_data/" + "local_train_splitByUser", "r") as f_rev:
    row = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[0] == '0' and items[1] not in user_map:
            user_map[items[1]]= line
        row += 1
        if (row % 100000 == 0):
            print("Build progress %d" % row)
                     
# python2
with open(file_name + "local_train_splitByUser", "r") as f_rev:
    row = 0
    tmp_uid = ""
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[0] == '0' and items[1] in user_map:
            print >> fo, user_map[items[1]]
            tmp_uid = items[1]
        if items[0] == '1' and tmp_uid == items[1]:
            print >> fo, line
        row += 1
        if (row % 100000 == 0):
            print("Save progress %d" % row)
# python3
#for key in user_map.keys():
#    print('\t'.join(user_map[key][0]), file = fo)
#    print('\t'.join(user_map[key][1]), file = fo)
