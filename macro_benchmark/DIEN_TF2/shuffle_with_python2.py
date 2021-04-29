dir_path = "/mnt/nvme2/chendi/BlueWhale/ai-matrix/macro_benchmark/DIEN_INTEL_TF2/"
file_name = dir_path + "pyspark_data/"
fo = open(file_name + "local_test_splitByUser_shuffled", "w")
user_map = {}

with open(file_name + "local_test_splitByUser", "r") as f_rev:
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[1] not in user_map:
            user_map[items[1]]= []
        user_map[items[1]].append((items))
                     
# python2
for key in user_map:
    print >> fo, '\t'.join(user_map[key][0])
    print >> fo, '\t'.join(user_map[key][1])
# python3
#for key in user_map.keys():
#    print('\t'.join(user_map[key][0]), file = fo)
#    print('\t'.join(user_map[key][1]), file = fo)
