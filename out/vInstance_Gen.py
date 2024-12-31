#! /usr/bin/env python

"""
vTbgenerator.py -- generate verilog module Testbench
generated bench file like this:

        fifo_sc #(
            .DATA_WIDTH ( 8 ),
            .ADDR_WIDTH ( 8 )
        )
         u_fifo_sc (
            .CLK   ( CLK                     ),
            .RST_N ( RST_N                   ),
            .RD_EN ( RD_EN                   ),
            .WR_EN ( WR_EN                   ),
            .DIN   ( DIN   [DATA_WIDTH-1 :0] ),
            .DOUT  ( DOUT  [DATA_WIDTH-1 :0] ),
            .EMPTY ( EMPTY                   ),
            .FULL  ( FULL                    )
        );

Usage:
      python vTbgenerator.py ModuleFileName.v

"""

import re
import sys
import chardet
import pyperclip


def delComment(Text):
    """removed comment"""
    # pattern = re.compile(r'^\s*//[^\r\n]*[\r\n]|//.*?$|/\*.*?\*/|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)
    pattern = re.compile(
        r'^\s*`pragma\s+protect\s+begin_protected.*`pragma protect end_protected|//.*?$|/\*.*?\*/|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE
    )
   
    return re.sub(pattern, lambda m: "" if m.group(0).startswith("/") else m.group(0), Text)


def delBlock(Text):
    """removed task and function block"""
    Text = re.sub(r"\Wtask\W[\W\w]*?\Wendtask\W", "\n", Text)
    Text = re.sub(r"\Wfunction\W[\W\w]*?\Wendfunction\W", "\n", Text)
    return Text


def findName(inText):
    """find module name and port list"""
    p = re.search(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*", inText)
    mo_Name = p.group(0).strip()
    return mo_Name


def paraDeclare(inText, portArr):
    """find parameter declare"""
    pat = r"\s" + portArr + r"\s[\w\W]*?(?:[;,]|(?:[)][)\s]*(?=\()))"
    ParaList = re.findall(pat, inText, re.MULTILINE)

    return ParaList


def portDeclare(inText, portArr):
    """find port declare, Syntax:
    input [ net_type ] [ signed ] [ range ] list_of_port_identifiers

    return list as : (port, [range])
    """
    portPat = portArr
    if isinstance(portArr, list):
        portPat = "|".join([f"(?:{port})" for port in portArr])

    portPat = "(" + portPat + ")"

    port_definition = re.compile(
        r"\b"
        + portPat
        + r""" (\s+(wire|reg|logic|int|integer|real)\s+)* (\s*signed\s+)*  (\s*\[.*?:.*?\]\s*)*
        (?P<port_list>.*?)
        (?= \binput\b | \boutput\b | \binout\b | ; | \) )
        """,
        re.VERBOSE | re.MULTILINE | re.DOTALL,
    )

    # pList = port_definition.findall(inText)
    pList = port_definition.finditer(inText)

    t = []
    last_line_num = None
    for ls in pList:
        line_num = inText[: ls.start()].count("\n")
        ls = tuple(["" if x is None else x for x in tuple(ls.groups())])
        if len(ls) >= 3:
            v = [x + (ls[0], line_num) for x in portDic(ls[-2:])]
            # add empty line for better visulization
            if last_line_num is not None and line_num != last_line_num + 1:
                t += [("", "", "empty", 0)]
            last_line_num = line_num
            t = t + v
    return t


def portDic(port):
    """delet as : input a =c &d;
    return list as : (port, [range])
    """
    pRe = re.compile(r"(.*?)\s*=.*", re.DOTALL)

    pRange = port[0]
    pList = port[1].split(",")
    pList = [i.strip() for i in pList if i.strip() != ""]
    pList = [(pRe.sub(r"\1", p), pRange.strip()) for p in pList]

    return pList


def formatPort(AllPortList, isPortRange=1):
    PortList = AllPortList[0] + AllPortList[1] + AllPortList[2]

    str = ""
    if PortList != []:
        l1 = max([len(i[0]) for i in PortList]) + 2
        l3 = max(24, l1)

        strList = []
        for pl in AllPortList:
            if pl != []:
                # str = ',\n'.join([' ' * 4 + '.' + i[0].ljust(l3) + '( ' + (i[0].ljust(l1)) + ' )' for i in pl])
                str = "\n".join(
                    [
                        (
                            (" " * 4 + "." + i[0].ljust(l3) + "( " + (i[0].ljust(l1)) + " )" + (" " if i is pl[-1] else ",") + " // " + i[2] + i[1])
                            if i[2] != "empty"
                            else ""
                        )
                        for i in pl
                    ]
                )
                strList = strList + [str]

        str = ",\n\n".join(strList)

    return str


def formatDeclare(PortList, portArr, initial=""):
    str = ""

    if PortList != []:
        str = "\n".join([(portArr.ljust(4) + "  " + (i[1] + min(len(i[1]), 1) * "  " + i[0]) + ";") if i[2] != "empty" else "" for i in PortList])
    return str


def formatPara(ParaList):
    paraDec = ""
    paraDef = ""
    if ParaList != []:
        s = "|".join(ParaList) + "|"
        # pat = r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*([\w\W]*?)\s*[;,)]'
        pat = r"([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*([^|]*)\s*(?:[;,)]\s*\|)"

        p = re.findall(pat, s)

        l1 = max([len(i[0]) for i in p])
        l2 = max([len(i[1]) for i in p])
        paraDec = "\n".join(["parameter %s = %s;" % (i[0].strip().ljust(l1 + 1), i[1].strip().ljust(l2)) for i in p])
        paraDefStr = "\n".join(["    ." + i[0].strip().ljust(l1 + 1) + "( " + i[0].strip().ljust(l2) + " ),  // " + i[1].strip() for i in p[:-1]])
        paraDefStr += "\n    ." + p[-1][0].strip().ljust(l1 + 1) + "( " + p[-1][0].strip().ljust(l2) + " )   // " + p[-1][1].strip()  # last one without comma
        paraDef = "#(\n" + paraDefStr + "\n) "
    return paraDec, paraDef


def writeTestBench(input_file):
    """write testbench to file"""
    with open(input_file, "rb") as f:
        f_info = chardet.detect(f.read())
        f_encoding = f_info["encoding"]
    with open(input_file, encoding=f_encoding) as inFile:
        inText = inFile.read()

    # removed comment,task,function
    inText = delComment(inText)
    inText = delBlock(inText)

    # moduel ... endmodule  #
    moPos_begin = re.search(r"(\b|^)module\b", inText).end()
    moPos_end = re.search(r"\bendmodule\b", inText).start()
    inText = inText[moPos_begin:moPos_end]

    name = findName(inText)
    paraList = paraDeclare(inText, "parameter")
    paraDec, paraDef = formatPara(paraList)

    ioPadAttr = ["input", "output", "inout"]
    # input = portDeclare(inText, ioPadAttr[0])
    # output = portDeclare(inText, ioPadAttr[1])
    # inout = portDeclare(inText, ioPadAttr[2])
    # portList = formatPort([input, output, inout])
    # input = formatDeclare(input, 'reg')
    # output = formatDeclare(output, 'wire')
    # inout = formatDeclare(inout, 'wire')

    # declare in order
    allPort = portDeclare(inText, ioPadAttr)
    portList = formatPort([allPort, [], []])
    portDecl = formatDeclare(allPort, "wire")
    # write Instance

    # module_parameter_port_list
    output_str = ""
    if paraDec != "":
        output_str += "// %s Parameters\n%s\n" % (name, paraDec)

    # list_of_port_declarations
    # print("// %s Inputs\n%s\n" % (name, input))
    # print("// %s Outputs\n%s\n" % (name, output))
    # if(inout != ''):
    #     print("// %s Bidirs\n%s\n" % (name, inout))o system
    output_str += "//---- %s ports ----\n%s\n" % (name, portDecl)

    # UUT
    output_str += "%s %s u_%s (\n%s\n);" % (name, paraDef, name, portList)

    print(output_str)
    print("------------------------------------------------")
    print(" * Contents also Copy to system clipboard *")
    pyperclip.copy(output_str)


if __name__ == "__main__":
    writeTestBench(sys.argv[1])
