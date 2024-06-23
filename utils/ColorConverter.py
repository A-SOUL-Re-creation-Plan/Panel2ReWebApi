def rgbToInt32(r, g, b):
    color = int((0xFF << 24) | (r << 16) | (g << 8) | b)
    return color


def int32ToRGB(int32):
    r = int(int32 >> 16) & 0xFF
    g = int(int32 >> 8) & 0xFF
    b = int(int32 >> 0) & 0xFF
    return r,g,b


def rgbToHex(r, g, b):
    h = str('#')
    h += str(hex(r)).replace('0x','') + str(hex(g)).replace('0x','') + str(hex(b)).replace('0x','')
    return h

def hexToRGB(hex_c):
    r = int(hex_c[1:3],16)
    g = int(hex_c[3:5],16)
    b = int(hex_c[5:7],16)
    return r,g,b

def int32ToHex(int32):
    r,g,b = int32ToRGB(int32)
    h = rgbToHex(r,g,b)
    return h
