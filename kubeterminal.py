import datetime
import base64
import re
import argparse 
import os

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit,VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import get_app
from prompt_toolkit.widgets import SystemToolbar
from prompt_toolkit.widgets import Frame, RadioList, VerticalLine, HorizontalLine, TextArea
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.keys import Keys
from prompt_toolkit import eventloop
from prompt_toolkit.shortcuts import yes_no_dialog
from prompt_toolkit.utils import Event
from prompt_toolkit.filters import to_filter

from kubectl import namespaces,pods,nodes,windowCmd
from application import state,lexer
from kubectl import cmd 
from application import globals

#CLI args
parser = argparse.ArgumentParser()
parser.add_argument('--no-dynamic-title', action="store_true", help='Do not set command window title to show NS, node and pod.')
parser.add_argument('--compact-windows', action="store_true", help='Set namespace, node and pod windows to more compact size.')
parser.add_argument('--even-more-compact-windows', action="store_true", help='Set namespace, node and pod windows to even more compact size.')
args = parser.parse_args()

applicationState = state#state.State()

applicationState.content_mode=globals.WINDOW_POD

namespaceWindowSize=27
nodeWindowSize=53
podListWindowSize=80
if args.compact_windows == True:
    namespaceWindowSize=20
    nodeWindowSize=30
    podListWindowSize=50
if args.even_more_compact_windows == True:
    namespaceWindowSize=20
    nodeWindowSize=10
    podListWindowSize=30


enableMouseSupport = False
enableScrollbar = False

#TODO: refactor code, all code

def updateState():
    
    selected_namespace=namespaceWindow.current_value
    selected_node=nodeListArea.current_value
    selected_pod=str(podListArea.buffer.document.current_line).strip()

    if applicationState.selected_pod != selected_pod:
        #somethingSelected=applicationState.selected_pod
        applicationState.selected_pod = selected_pod
        #f somethingSelected != "":
        #    updateUI("selectedpod")

    if applicationState.current_namespace != selected_namespace:
        applicationState.current_namespace = selected_namespace
        #reset position
        state.cursor_line = -1

        updateUI("namespacepods")

    if applicationState.selected_node != selected_node:
        applicationState.selected_node = selected_node
        #reset position
        state.cursor_line = -1

        updateUI("nodepods")

def updateUI(updateArea):
    
    if updateArea == "selectedpod":
        appendToOutput(applicationState.selected_pod)

    if updateArea == "nodepods" or updateArea == "namespacepods":
        moveToLine=state.cursor_line
        ns = applicationState.current_namespace
        contentList = ""
        title = ""
        if applicationState.content_mode == globals.WINDOW_POD:
            (contentList,title) = windowCmd.getPods(ns,applicationState.selected_node)
        if applicationState.content_mode == globals.WINDOW_SVC:
            (contentList,title) = windowCmd.getServiceList(ns)
        if applicationState.content_mode == globals.WINDOW_CM:
            (contentList,title) = windowCmd.getConfigMapList(ns)
        if applicationState.content_mode == globals.WINDOW_SECRET:
            (contentList,title) = windowCmd.getSecretList(ns)
        if applicationState.content_mode == globals.WINDOW_SF:
            (contentList,title) = windowCmd.getStatefulSetList(ns)
        if applicationState.content_mode == globals.WINDOW_RS:
            (contentList,title) = windowCmd.getReplicaSetList(ns)
        if applicationState.content_mode == globals.WINDOW_DS:
            (contentList,title) = windowCmd.getDaemonSetList(ns)
                
        podListArea.text=contentList
        podListAreaFrame.title=title
        setCommandWindowTitle()
        if moveToLine > 0:
            #if pod window cursor line was greater than 0 
            #then move to that line
            #appendToOutput("Should move to line: %d" % moveToLine)
            podListArea.buffer.cursor_down(moveToLine)


kb = KeyBindings()
# Global key bindings.

@kb.add('tab')
def tab_(event):
    updateState()
    #refresh UI
    focus_next(event)

@kb.add('s-tab')
def stab_(event):
    updateState()
    #refresh UI
    focus_previous(event)

@kb.add('escape')
def exit_(event):
    """
    Pressing Esc will exit the user interface.

    Setting a return value means: quit the event loop that drives the user
    interface and return this value from the `CommandLineInterface.run()` call.
    """
    event.app.exit()

@kb.add('c-d')
def describepod_(event):
    applicationState.selected_pod=str(podListArea.buffer.document.current_line).strip()
    executeCommand("describe")

@kb.add('c-y')
def yamlResource_(event):
    applicationState.selected_pod=str(podListArea.buffer.document.current_line).strip()
    executeCommand("yaml")

@kb.add('c-l')
def logspod_(event):
    applicationState.selected_pod=str(podListArea.buffer.document.current_line).strip()
    executeCommand("logs")

@kb.add('c-r')
def logspod_(event):
    #refresh pods
    updateState()
    updateUI("namespacepods")

@kb.add('G')
def toendofoutputbuffer_(event):    
    outputArea.buffer.cursor_down(outputArea.document.line_count)

@kb.add('W')
def togglewrap_(event):    
    toggleWrap()

#search keyboard
@kb.add('/')
def searchbuffer_(event):
    #search both pods and output window at the same time
    if (len(command_container.text)>0):
        #if length of text is command container is > 0
        # assume that command is currently written
        #ignore search
        command_container.text=command_container.text+"/"
        command_container.buffer.cursor_right(len(command_container.text))
        
        return
    
    layout.focus(command_container)
    command_container.text="/"
    command_container.buffer.cursor_right()

#content windows
namespaceWindow = RadioList(namespaces.list())
namespaceWindowFrame= Frame(namespaceWindow,title="Namespaces",height=8,width=namespaceWindowSize)

nodeListArea = RadioList(nodes.list())
nodeWindowFrame= Frame(nodeListArea,title="Nodes",height=8,width=nodeWindowSize)

upper_left_container = VSplit([namespaceWindowFrame, 
                #HorizontalLine(),
                #Window(height=1, char='-'),
                nodeWindowFrame])

def setCommandWindowTitle():
    selected_namespace=namespaceWindow.current_value
    selected_node=nodeListArea.current_value
    selected_pod=str(podListArea.buffer.document.current_line).strip()

    if selected_namespace == "all-namespaces":
        fields = selected_pod.split()
        selected_namespace = fields[0]
        selected_pod = " ".join(fields[1:])
    title = ""
    if applicationState.content_mode == globals.WINDOW_POD:
        title = "NS: %s, NODE: %s, POD: %s" % (selected_namespace,selected_node,selected_pod)
    if applicationState.content_mode == globals.WINDOW_SVC:
        title = "NS: %s, SERVICE: %s" % (selected_namespace,selected_pod)
    if applicationState.content_mode == globals.WINDOW_CM:
        title = "NS: %s, CONFIGMAP: %s" % (selected_namespace,selected_pod)
    if applicationState.content_mode == globals.WINDOW_SECRET:
        title = "NS: %s, SECRET: %s" % (selected_namespace,selected_pod)
    if applicationState.content_mode == globals.WINDOW_SF:
        title = "NS: %s, STATEFULSET: %s" % (selected_namespace,selected_pod)
    if applicationState.content_mode == globals.WINDOW_RS:
        title = "NS: %s, REPLICASET: %s" % (selected_namespace,selected_pod)
    if applicationState.content_mode == globals.WINDOW_DS:
        title = "NS: %s, DAEMONSET: %s" % (selected_namespace,selected_pod)

    title = title.replace("<none>", '')
    title = re.sub(' +', ' ', title)
    commandWindowFrame.title = title

#listens cursor changes in pods list
def podListCursorChanged(buffer):
    #when position changes, save cursor position to state
    state.cursor_line = buffer.document.cursor_position_row

    if args.no_dynamic_title == False:
        setCommandWindowTitle()

#pods window
podListArea = TextArea(text="", 
                multiline=True,
                wrap_lines=False,
                scrollbar=enableScrollbar,
                lexer=lexer.PodStatusLexer(),
                read_only=True                
                )

#add listener to cursor position changed
podListArea.buffer.on_cursor_position_changed=Event(podListArea.buffer,podListCursorChanged)
podListArea.window.cursorline = to_filter(True)
podListAreaFrame = Frame(podListArea,title="Pods",width=podListWindowSize)

left_container = HSplit([upper_left_container, 
                #HorizontalLine(),
                #Window(height=1, char='-'),
                podListAreaFrame])

#print(namespaceWindow.current_value)
#output area to output debug etc stuff
outputArea = TextArea(text="", 
                    multiline=True,
                    wrap_lines=False,
                    lexer=lexer.OutputAreaLexer(),
                    scrollbar=enableScrollbar,
                    read_only=True)
outputAreaFrame= Frame(outputArea,title="Output")

content_container = VSplit([
    # One window that holds the BufferControl with the default buffer on
    # the left.
    left_container,
    # A vertical line in the middle. We explicitly specify the width, to
    # make sure that the layout engine will not try to divide the whole
    # width by three for all these windows. The window will simply fill its
    # content by repeating this character.
    #VerticalLine(),
    #Window(width=1, char='|')
    
    # Display the text 'Hello world' on the right.
    #Window(content=FormattedTextControl(text='Hello world, Escape to Quit'))
    outputAreaFrame

])

def appendToOutput(text,cmdString="",overwrite=False):

    if text is None or "No resources found" in text:    
        return
    
    #TODO: option to set UTC or local
    #now = datetime.datetime.utcnow().isoformat()
    now = datetime.datetime.now().isoformat()
    if cmdString == "":
        header = "=== %s ===" % now
    else:
        header = "=== %s - %s ===" % (now,cmdString)
    
    if outputArea.text == "":        
        outputArea.text="\n".join([header,text,""])
    else:
        outputArea.text="\n".join([outputArea.text,header,text,""])
    
#    outputArea.buffer.cursor_position=len(outputArea.text)
    outputIndex=outputArea.text.find(header)
    outputArea.buffer.cursor_position=outputIndex#len(outputArea.text)
    outputArea.buffer.cursor_down(30)


#command handler for shell
def commandHander(buffer):
    #check incoming command
    cmdString = buffer.text
    executeCommand(cmdString)

#actual command handler, can be called from other sources as well
def executeCommand(cmdString):
    refreshUIAfterCmd = False
    text=""
    cmdcmdString = cmdString.strip()
    if cmdString == "":
        return

    if cmdString == "help":
        text="""KubeTerminal

Helper tool for Kubernetes.

This output window shows output of commands.
"Selected pod/resource" is the resource where cursor is in the Resources window.

Key bindings

- ESC - exit program.
- <ctrl-l>, show logs of currently selected pod (without any options).
- <ctrl-d>, show description of currently selected resource (without any options).
- <ctrl-y>, show YAML of currently selected resource.
- <ctrl-r>, refresh UI.
- <shift-g>, to the end of Output-window buffer.
- <shift-w>, toggle wrapping in Output-window.
- / -  search string in Output-window.

Commands:

- help - this help.
- cert <data key> - show certificate of secret value using openssl.
- clip - copy Output-window contents to clipboard.
- cls - clear Output-window.
- cm [<configmap-name>] [<key-name>] [--decode] - get configmaps in selected namespace. If first arg, then show yaml of given configmap. If also second arg, then show value of given key. If --decode is present, value is base64 decoded.
- decode <data key> - decode base64 encoded secret or configmap value.
- delete [--force] - delete currently selected pod, optionally force delete.
- describe <describe options> - show description of currently selected resource.
- exec [-c <container_name>] <command> - exec command in currently selected pod.
- ingress [<ingress name>] - show ingresses in selected namespace. If name is given, show yaml of ingress.
- json - get JSON of currently selected resource.
- ku <cmds/opts/args> - execute kubectl in currently selected namespace.
- labels - show labels of currently selected pod.
- logs [-c <container_name>] - show logs of currently selected pod.
- node <node name> - show description of given node, or currently selected node.
- secret [<secret-name>] [<key-name>] [--decode | --cert] - get secrets in selected namespace. If first arg, then show yaml of given secret. If also second arg, then show value of given key. If --decode is present, value is base64 decoded. If --cert is present, value is assumed to be TLS certificate and openssl is used to decode it.
- save [<filename>] - save Output-window contents to a file.
- shell <any shell command> - executes any shell command.
- svc [nodeport | <service name>] - show services in selected namespace. If nodeport, shows only NodePort services. If service name, shows yaml of the service.
- top [-c | -l <label=value> | -n | -g] - show top of pods/containers/labels/nodes. Use -g to show graphics.
- window [pod | svc | cm | secret | sf | rs | ds] - Set resource type for window.
- workers [-d] - get worker node resource allocation. Use -d to describe all worker nodes.
- wrap - toggle wrapping in Output-window.
- yaml - get YAML of currently selected resource.

"""
    def getResourceNameAndNamespaceName():
        podLine = applicationState.selected_pod
        namespace=""
        resourceName=""
        if podLine != "":
            fields=podLine.split()
            if applicationState.current_namespace == "all-namespaces":
                resourceName=fields[1]
                namespace=fields[0]
            else:
                resourceName=fields[0]
                namespace=applicationState.current_namespace
        return (namespace,resourceName)

    def isAllNamespaces():
        return applicationState.current_namespace == "all-namespaces"

    def getCmdString(cmd, resource):
        resourceType = ""
        if applicationState.content_mode == globals.WINDOW_POD:
            resourceType = "pod"
        if applicationState.content_mode == globals.WINDOW_CM:
            resourceType = "cm"
        if applicationState.content_mode == globals.WINDOW_SVC:
            resourceType = "svc"
        if applicationState.content_mode == globals.WINDOW_SECRET:
            resourceType = "secret"
        if applicationState.content_mode == globals.WINDOW_SF:
            resourceType = "statefulset"
        if applicationState.content_mode == globals.WINDOW_RS:
            resourceType = "replicaset"
        if applicationState.content_mode == globals.WINDOW_DS:
            resourceType = "daemonset"
        
        if cmd == "describe":
            commandString ="ku describe %s %s" % (resourceType,resource)
        if cmd == "yaml":
            commandString ="ku get %s %s -o yaml" % (resourceType,resource)
        if cmd == "json":
            commandString ="ku get %s %s -o json" % (resourceType,resource)

        return commandString

    (namespace,resourceName)=getResourceNameAndNamespaceName()

    if cmdString.find("logs") == 0:
        if applicationState.content_mode == globals.WINDOW_POD:
            if namespace!="" and resourceName != "":
                options=cmdString.replace("logs","")
                cmdString = "logs " + resourceName
                text=pods.logs(resourceName,namespace,options)                
                index = text.find("choose one of: [")
                if index > -1:
                    text1 = text[0:index]
                    text2 = text[index:]
                    text2 = text2.replace("choose one of: [","choose one of:\n[")
                    text = "%s\n%s" % (text1, text2)
        else:
            text = "ERROR: Logs are available only for pods."

    if cmdString.find("describe") == 0:
        cmdString = getCmdString("describe",resourceName)

    if cmdString.find("yaml") == 0:
        cmdString = getCmdString("yaml",resourceName)

    if cmdString.find("json") == 0:
        cmdString = getCmdString("json",resourceName)

    if cmdString.find("label") == 0:
        if applicationState.content_mode == globals.WINDOW_POD:
            cmdString = "labels %s" % (resourceName)
            text=pods.labels(resourceName,namespace)
        else:
            text = "ERROR: Labels are currently available only for pods."

    if cmdString.find("decode") == 0:
        if applicationState.content_mode == globals.WINDOW_SECRET or applicationState.content_mode == globals.WINDOW_CM:
            cmdArgs = cmdString.split()
            if len(cmdArgs) > 1:
                key = cmdArgs[1]
                cmdString =""
                if applicationState.content_mode == globals.WINDOW_SECRET:
                    cmdString = "secret "
                if applicationState.content_mode == globals.WINDOW_CM:
                    cmdString = "cm "
                cmdString = "%s %s %s --decode " % (cmdString,resourceName, key)
            else:
                text = "ERROR: No key name given."
        else:
            text = "ERROR: Decode available only for secrets and configmaps."

    if cmdString.find("cert") == 0:
        if applicationState.content_mode == globals.WINDOW_SECRET:
            cmdArgs = cmdString.split()
            if len(cmdArgs) > 1:
                key = cmdArgs[1]
                cmdString = "secret %s %s --cert " % (resourceName, key)
            else:
                text = "ERROR: No key name given."
        else:
            text = "ERROR: cert available only for secrets."


    doBase64decode = False
    isCertificate = False
    if cmdString.find("secret") == 0 or cmdString.find("cm") == 0:
        kubeArg = "secret"
        if cmdString.find("cm")==0:
            kubeArg = "cm"
        cmdStringList = cmdString.split()
        if len(cmdStringList) == 1:
            cmdString = "ku get %s" % kubeArg
        elif len(cmdStringList) == 2:
            cmdString = "ku get %s %s -o yaml" % (kubeArg, cmdStringList[1])
        elif len(cmdStringList) >=3:
            jsonPath = cmdStringList[2]
            jsonPath = jsonPath.replace(".","\\.")
            cmdString = "ku get %s %s -o jsonpath='{.data.%s}'" % (kubeArg, cmdStringList[1], jsonPath)
            if len(cmdStringList) == 4 and cmdStringList[3] == "--decode":
                doBase64decode=True
            if kubeArg == "secret" and len(cmdStringList) == 4 and cmdStringList[3] == "--cert":
                doBase64decode=True
                isCertificate = True

    if cmdString.find("ku") == 0:
        namespace = " -n %s" % namespace        
        kuArgs = cmdString[2:]
        cmdString  = "shell kubectl%s %s" % (namespace, kuArgs.strip())

    if cmdString.find("ingress") == 0:
        if isAllNamespaces() == True:
            namespace=""
        else:
            namespace = " -n %s" % namespace        
        kuCmd = "get ingress "
        kuArgs = cmdString.split()
        if len(kuArgs) > 1:
            kuCmd = kuCmd + kuArgs[1] + " -o yaml"
        cmdString  = "shell kubectl%s %s" % (namespace, kuCmd)


    if cmdString.find("svc") == 0:
        if isAllNamespaces() == True:
            namespace=""
        else:
            namespace = " -n %s" % namespace        
        kuCmd = "get services "
        kuArgs = cmdString.split()
        if len(kuArgs) > 1:
            if kuArgs[1] == "nodeport":
                #show only nodeports
                kuCmd = kuCmd + " | grep NodePort"
            else:
                kuCmd = kuCmd + kuArgs[1] + " -o yaml"
        cmdString  = "shell kubectl%s %s" % (namespace, kuCmd)


    if cmdString.find("node") == 0:
        selectedNode=applicationState.selected_node
        options=cmdString.replace("node","").strip()
        text=nodes.describe(options,selectedNode)
        if options == "":
            options = selectedNode
        cmdString = "describe node %s " % options

    if cmdString.find("delete") == 0:
        if applicationState.content_mode == globals.WINDOW_POD:
            force=False
            if (cmdString.find("--force") > -1):
                force=True
            text=pods.delete(resourceName,namespace,force)
            cmdString = "delete pod %s" % resourceName
            #refreshUIAfterCmd = True
        else:
            text = "ERROR: delete is available only for pods."

    if cmdString.find("shell") == 0:
        shellCmd = cmdString.replace("shell","").strip()
        text=cmd.executeCmd(shellCmd)

    if doBase64decode == True:
        #text is assumed to hold base64 string, from secret or cm command
        text = text.replace("'","")
        text = base64.b64decode(text)
        text = str(text,"utf8")
    
    if isCertificate == True:
        #text is assumed to be certificate and openssl tool is assumed to present
        import subprocess,os
        fName = ".cert.tmp"
        certFile = open(fName,"w")
        certFile.write(text)
        certFile.close()
        text = subprocess.check_output(["openssl", "x509", "-text", "-noout", 
                                "-in", fName],stderr=subprocess.STDOUT,timeout=30)
        text = str(text,'utf-8')
        if os.path.exists(fName):
            os.remove(fName)

    if cmdString.find("exec") == 0:
        if applicationState.content_mode == globals.WINDOW_POD:
            command = cmdString.replace("exec","").strip()
            cmdString = "exec %s %s" % (resourceName,command)
            text=pods.exec(resourceName,namespace,command)
        else:
            text = "ERROR: exec is available only for pods."


    if cmdString.find("top") == 0:
        topCmd=cmdString
        if cmdString.find("-l") > -1:
            cmdString = cmdString.replace("-l","label")
        if cmdString.find("-c") > -1:
            cmdString = "top pod %s" % (resourceName)
        if cmdString.find("-n") > -1:
            cmdString = "top nodes"
        
        doAsciiGraph=False
        if topCmd.find("-g") > -1:
            doAsciiGraph = True
            topCmd = topCmd.replace("-g","")

        
        text=pods.top(resourceName,namespace,topCmd,isAllNamespaces(),doAsciiGraph)

    if cmdString.find("cls") == 0:
        clearOutputWindow()

    if cmdString.find("wrap") == 0:
        toggleWrap()

    if cmdString.find("/") == 0:
        #searching
        applicationState.searchString=cmdString[1:]
        #appendToOutput("TODO: search: %s" % applicationState.searchString, cmdString=cmdString)

    if cmdString.find("save") == 0:
        #save Output-window to a file
        cmdArgs = cmdString.split()
        if len(cmdArgs) > 1:
            #filename is the second argument
            filename = cmdArgs[1]
        else:
            filename = "kubeterminal_output_%s.txt" % datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        with open(filename, "w") as outputFile:
            outputFile.write(outputArea.text)
        text="Output saved to file '%s'." % filename


    if cmdString.find("work") == 0:
        #worker node statistics

        params=[]
        if cmdString.find("-d") > -1:
           params.append("describe")
 
        nodeStats = nodes.describeNodes("worker",params)
        
        text=nodeStats

    if cmdString.find("clip") == 0:
        #copy output window contents to clipboard
        import pyperclip
        pyperclip.copy(outputArea.text)
        text="Output window contents copied to clipboard."

    if cmdString.find("win") == 0:
        #window command to select content for "pod"-window
        cmdArgs = cmdString.split()
        if len(cmdArgs) > 1:
            applicationState.content_mode = "WINDOW_%s" % (cmdArgs[1].upper())
            updateUI("namespacepods")
        else:
            text = "Available commands/Resource types:\n"
            for resourceType in globals.WINDOW_LIST:
                text="%swindow %s\n" % (text,resourceType.lower().replace("window_",""))


    if text != "":
        appendToOutput(text,cmdString=cmdString)
        #appendToOutput("\n".join([outputArea.text,text]),cmd=cmd)
        #outputArea.text="\n".join([outputArea.text,text])
    
    if refreshUIAfterCmd == True:
        updateUI("namespacepods")
        
def commandPrompt(line_number, wrap_count):
    return "command>"

def clearOutputWindow():
    outputArea.text = ""

def toggleWrap():
    outputArea.wrap_lines = not outputArea.wrap_lines

command_container = TextArea(text="", multiline=False,accept_handler=commandHander,get_line_prefix=commandPrompt)
commandWindowFrame= Frame(command_container,title="KubeTerminal (Ctrl-d to describe pod, Ctrl-l to show logs, Esc to exit, Tab to switch focus and refresh UI, 'help' for help)",height=4)


root_container = HSplit([content_container, 
     #           HorizontalLine(),
                #Window(height=1, char='-'),
                commandWindowFrame])

layout = Layout(root_container)

app = Application(layout=layout,
                key_bindings=kb,
                full_screen=True,             
                mouse_support=enableMouseSupport
                )
app.run()