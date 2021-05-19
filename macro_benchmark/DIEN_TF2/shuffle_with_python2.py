import sys

file_name = sys.argv[1]
fo = open(file_name + "local_train_splitByUser_shuffled", "w")

user_map = {}

with open(file_name + "local_train_splitByUser_full", "r") as f_rev:
    row = 0
    for line in f_rev.readlines():
        line = line.strip()
        items = line.split("\t")
        if items[1] not in user_map:
            user_map[items[1]]= []
        user_map[items[1]].append((items))
        row += 1
        if (row % 100000 == 0):
            print("Read progress %d" % row)
                     
# python2
row = 0
for key in user_map:
    print >> fo, '\t'.join(user_map[key][0])
    print >> fo, '\t'.join(user_map[key][1])
    row += 2
    if (row % 100000 == 0):
       print("Save progress %d" % row)
# python3
#for key in user_map.keys():
#    print('\t'.join(user_map[key][0]), file = fo)
#    print('\t'.join(user_map[key][1]), file = fo)
