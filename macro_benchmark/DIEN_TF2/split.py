import sys

file_name = sys.argv[1]
fo_0 = open(file_name + "local_train_splitByUser_splitted_0", "w")
fo_1 = open(file_name + "local_train_splitByUser_splitted_1", "w")
user_map = {}

# python2
with open(file_name + "local_train_splitByUser", "r") as f_rev:
    row = 0
    tmp_uid = ""
    user_count = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[0] == '0':
            if user_count % 2 == 0:
                print >> fo_0, line
            else:
                print >> fo_1, line
            tmp_uid = items[1]
        if items[0] == '1' and tmp_uid == items[1]:
            if user_count % 2 == 0:
                print >> fo_0, line
            else:
                print >> fo_1, line
            user_count += 1
        row += 1
        if (row % 100000 == 0):
            print("Save progress %d" % row)
# python3
#for key in user_map.keys():
#    print('\t'.join(user_map[key][0]), file = fo)
#    print('\t'.join(user_map[key][1]), file = fo)
