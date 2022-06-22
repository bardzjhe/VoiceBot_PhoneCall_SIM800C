def getConfig(filepath):
    setting = {}
    f = open(filepath, "r")
    for i in f:
        string = i.split("=")
        setting[string[0].strip()] = string[1].strip()
    f.close()
    return setting #return type is dict

def setConfig(filepath, newSetting):
    f = open(filepath, "w")
    for i in newSetting:
        f.write(str(i) + " = " + str(newSetting[i]) + "\n")
    f.close()