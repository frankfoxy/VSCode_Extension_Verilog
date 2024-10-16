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

import io


def print_to_str(*args, **kwargs):
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    contents = output.getvalue()
    output.close()
    return contents


def delComment(Text):
    """removed comment"""
    single_line_comment = re.compile(r"//(.*)$", re.MULTILINE)
    multi_line_comment = re.compile(r"/\*(.*?)\*/", re.DOTALL)
    Text = multi_line_comment.sub("\n", Text)
    Text = single_line_comment.sub("\n", Text)
    return Text


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
            v = portDic(ls[-2:])[0] + (ls[0], line_num)
            # add empty line for better visulization
            if last_line_num is not None and line_num != last_line_num + 1:
                t += [("", "", "empty", 0)]
            last_line_num = line_num
            t = t + [v]
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


def findPort(PortList, port_type, name_pat):
    ports = [x for x in PortList if ((x[2] != "empty" and x[2] == port_type) or port_type == "") and re.search(name_pat, x[0], re.IGNORECASE) is not None]
    return ports[0][0] if len(ports) >= 1 else ""


def formatDeclareEx(PortList, PortTypeList, portArrList, initial_list=[]):
    str = ""
    initial_list = [" = " + x if x != "" else x for x in initial_list]

    if PortList != []:
        str = "\n".join(
            [
                (
                    (
                        portArrList[PortTypeList.index(i[2])].ljust(4)
                        + "  "
                        + (i[1] + min(len(i[1]), 1) * "  " + i[0])
                        + initial_list[PortTypeList.index(i[2])]
                        + ";"
                    )
                    if i[2] != "empty"
                    else ""
                )
                for i in PortList
            ]
        )
    return str


def formatDeclare(PortList, portArr, initial=""):
    str = ""
    if initial != "":
        initial = " = " + initial

    if PortList != []:
        str = "\n".join([(portArr.ljust(4) + "  " + (i[1] + min(len(i[1]), 1) * "  " + i[0]) + initial + ";") if i[2] != "empty" else "" for i in PortList])
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

    # preDec = "\n".join(["parameter %s = %s;\n" % ("PERIOD".ljust(l1 + 1), "10".ljust(l2))])
    # paraDec = preDec + paraDec
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
    # input = formatDeclare(input, "reg", "0")
    # output = formatDeclare(output, "wire")
    # inout = formatDeclare(inout, "wire")

    allPort = portDeclare(inText, ioPadAttr)
    portList = formatPort([allPort, [], []])
    portDecl = formatDeclareEx(allPort, ioPadAttr, ["reg", "wire", "wire"], ["0", "", ""])

    # write testbench
    output_str = ""
    timescale = "`timescale  1ns / 1ps\n"
    output_str += print_to_str(timescale)
    output_str += print_to_str("module tb_%s;\n" % name)

    output_str += "  parameter CLK_PERIOD = 10;"
    # module_parameter_port_list
    if paraDec != "":
        output_str += print_to_str("// %s Parameters\n%s\n" % (name, paraDec))

    # list_of_port_declarations
    # output_str += print_to_str("// %s Inputs\n%s\n" % (name, input))
    # output_str += print_to_str("// %s Outputs\n%s\n" % (name, output))
    # if inout != "":
    #     output_str += print_to_str("// %s Bidirs\n%s\n" % (name, inout))
    output_str += print_to_str("// %s ports\n%s\n" % (name, portDecl))

    # output_str += print_to_str clock & rst
    clk_name = findPort(allPort, "input", r"[\w_]*clk[\w_]*|[\w_]*clock[\w_]*")
    if clk_name != "":
        output_str += print_to_str("""  initial forever #(CLK_PERIOD / 2) %s = ~%s;""" % (clk_name, clk_name))
    rst_name = findPort(allPort, "input", r"[\w_]*rst[\w_]*|[\w_]*reset[\w_]*")
    if rst_name != "":
        output_str += print_to_str("""  initial #(CLK_PERIOD * 2) %s = 1;\n""" % rst_name)
    # print(clk_name, rst_name)

    # UUT
    output_str += print_to_str("%s %s u_%s (\n%s\n);" % (name, paraDef, name, portList))

    # output_str += print_to_str operation
    operation = """
  initial begin
      $stop(0);
  end
"""
    output_str += print_to_str(operation)
    output_str += print_to_str("endmodule")

    print(output_str)
    print("------------------------------------------------")
    print(" * Contents also Copy to system clipboard *")
    pyperclip.copy(output_str)


if __name__ == "__main__":
    writeTestBench(sys.argv[1])
