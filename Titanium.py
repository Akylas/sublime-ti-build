import sublime
import sublime_plugin
import json
import subprocess
import re
import os
import plistlib

PLUGIN_FOLDER = os.path.dirname(os.path.realpath(__file__))
PLUGIN_NAME = "Titanium"
SETTINGS_FILE = PLUGIN_NAME + ".sublime-settings"
SETTINGS_PREFIX = PLUGIN_NAME.lower() + '_'

settings = sublime.load_settings(SETTINGS_FILE)

def get_setting(key, default=None, view=None):
    try:
        if view == None:
            view = sublime.active_window().active_view()
        s = view.settings()
        if s.has(SETTINGS_PREFIX + key):
            return s.get(SETTINGS_PREFIX + key)
    except:
        pass
    if settings.has(SETTINGS_PREFIX + key):
        return settings.get(SETTINGS_PREFIX + key, default)
    else:
        return default

class TitaniumCommand(sublime_plugin.WindowCommand):

    def plistStringFromProvFile(self, path):
        beginToken = '<?xml'
        endToken = '</plist>'
        f = open(path, "rb")
        data =  str(f.read())
        f.close()
        begin = data.find(beginToken)
        end = data.find(endToken) + len(endToken) 
        return data[begin:end]

    def getUUIDAndName(self, certPath):
        print ("getUUIDAndName " + certPath)
        plistString = self.plistStringFromProvFile(certPath).replace('\\n', "")
        plist = plistlib.readPlistFromBytes(bytes(plistString, 'UTF-8'))
        print (plist)
        return [plist['UUID'],plist['TeamName'], plist['TeamIdentifier'][0]]

    def copyProvisioningProfile(self, certPath, certName):
        dest = os.path.join(os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles'), certName + '.mobileprovision')
        if (not os.path.isfile(dest)):
            print ("copying " + certPath + " to " +  dest)
            shutil.copyfile(certPath, dest)

    def updateIOsBuildInTiApp(self):
        #update build number
        tiappPath = os.path.join(self.project_folder, "tiapp.xml")
        if (os.path.isfile(tiappPath)):
            f2 = open(tiappPath, "r")
            tiapp = f2.read()
            f2.close()
            m = re.search('(?<=<key>CFBundleVersion<\/key>)(\s*<string>)([\d]*)(?=<\/string>)',tiapp)
            if (m != None):
                version = int(m.group(2)) + 1
                print ('updating tiapp CFBundleVersion to ' + str(version))
                tiapp = re.sub('<key>CFBundleVersion</key>\s*<string>[\d]*</string>', '<key>CFBundleVersion</key><string>' + str(version) + '</string>',tiapp)
                f2 = open(tiappPath, "w")
                f2.write(tiapp)
                f2.close()
        else:
            print ("tiapp.xml doesnt exist: " + tiappPath)

    def updateAndroidBuildInTiApp(self):
        #update build number
        tiappPath = os.path.join(self.project_folder, "tiapp.xml")
        if (os.path.isfile(tiappPath)):
            f2 = open(tiappPath, "r")
            tiapp = f2.read()
            f2.close()
            m = re.search('(?<=android:versionCode=")([\d]*)(?=")',tiapp)
            if (m != None):
                version = int(m.group(1)) + 1
                print ('updating tiapp android:versionCode to ' + str(version))
                tiapp = re.sub('(?<=android:versionCode=")[\d]*(?=")', str(version),tiapp)
                f2 = open(tiappPath, "w")
                f2.write(tiapp)
                f2.close()
        else:
            print ("tiapp.xml doesnt exist: " + tiappPath)

    def handleError(self):
        sublime.log_commands(True)
        sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})

    def run(self, *args, **kwargs):
        if ('titaniumMostRecent' in globals() and 'titaniumMostRecent' in kwargs and kwargs['titaniumMostRecent'] == True):
            self.window.run_command("exec", {"cmd": titaniumMostRecent})
            return

        self.node              = get_setting("nodejs", "/usr/local/bin/node")
        self.cli              = get_setting("titaniumCLI", "/usr/local/bin/titanium")
        self.android          = get_setting("androidSDK", "/opt/android-sdk") + "/tools/android"
        self.loggingLevel     = get_setting("loggingLevel", "info")
        self.iosVersion       = str(get_setting("iosVersion", "unknown"))
        self.outputDir       = str(get_setting("outputDir", ""))
        self.certsDir       = str(get_setting("iosCertsDir", "unknown"))
        folders = self.window.folders()
        if len(folders) <= 0:
            self.show_quick_panel(["ERROR: Must have a project open"], None)
        else:
            if len(folders) == 1:
                self.multipleFolders = False
                self.project_folder = folders[0]
                self.project_sdk = self.get_project_sdk_version()
                self.pick_platform()
            else:
                self.multipleFolders = True
                self.pick_project_folder(folders)

    def pick_project_folder(self, folders):
        folderNames = []
        for folder in folders:
            index = folder.rfind('/') + 1
            if index > 0:
                folderNames.append(folder[index:])
            else:
                folderNames.append(folder)

        # only show most recent when there is a command stored
        if 'titaniumMostRecent' in globals():
            folderNames.insert(0, 'most recent configuration')

        self.show_quick_panel(folderNames, self.select_project)

    def select_project(self, select):
        folders = self.window.folders()
        if select < 0:
            return

        # if most recent was an option, we need subtract 1
        # from the selected index to match the folders array
        # since the "most recent" option was inserted at the beginning
        if 'titaniumMostRecent' in globals():
            select = select - 1

        if select == -1:
            self.window.run_command("exec", {"cmd": titaniumMostRecent})
        else:
            self.project_folder = folders[select]
            self.project_sdk = self.get_project_sdk_version()
            self.pick_platform()


    def pick_platform(self):
        self.preCmd = [self.node, self.cli, "--sdk", self.project_sdk, "--project-dir", self.project_folder]
        self.platforms = ["android", "ios", "mobileweb", "clean"]

        # only show most recent when there are NOT multiple top level folders
        # and there is a command stored
        if self.multipleFolders == False and 'titaniumMostRecent' in globals():
            self.platforms.insert(0, 'most recent configuration')

        self.show_quick_panel(self.platforms, self.select_platform)

    def select_platform(self, select):
        if select < 0:
            return
        self.platform = self.platforms[select]

        if self.platform == "most recent configuration":
            self.window.run_command("exec", {"cmd": titaniumMostRecent})
        elif self.platform == "ios":
            self.targets = ["simulator", "simulator auto", "device", "dist-adhoc", "dist-appstore"]
            self.show_quick_panel(self.targets, self.select_ios_target)
        elif self.platform == "android":
            self.targets = ["emulator", "device", "dist-adhoc", "dist-playstore"]
            self.show_quick_panel(self.targets, self.select_android_target)
        elif self.platform == "mobileweb":
            self.targets = ["development", "production"]
            self.show_quick_panel(self.targets, self.select_mobileweb_target)
        else:  # clean project
            self.window.run_command("exec", {"cmd": [self.node, self.cli, "clean", "--no-colors", "--project-dir", self.project_folder]})

    # Sublime Text 3 requires a short timeout between quick panels
    def show_quick_panel(self, options, done):
        sublime.set_timeout(lambda: self.window.show_quick_panel(options, done), 10)

    # get the current project's SDK from tiapp.xml
    def get_project_sdk_version(self):
        cmd = [self.node, self.cli, "project", "sdk-version", "--project-dir", self.project_folder, "--log-level", "error", "--output", "json"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        info = json.loads(result.decode('utf-8'))
        print(info)
        return info['sdk-version']

    def run_titanium(self, options=[]):
        cmd = self.preCmd +["build", "--platform", self.platform, "--log-level", self.loggingLevel, "--no-colors"]
        if (self.iosVersion is not "unknown" and self.iosVersion is not ""):
            options.extend(["--ios-version", self.iosVersion])
        cmd.extend(options)
        print (" ".join(cmd))

        # save most recent command
        global titaniumMostRecent
        titaniumMostRecent = cmd

        self.window.run_command("exec", {"cmd": cmd})

    #--------------------------------------------------------------
    # MOBILE WEB
    #--------------------------------------------------------------

    def select_mobileweb_target(self, select):
        if select < 0:
            return
        self.run_titanium(["--deploy-type", self.targets[select]])

    #--------------------------------------------------------------
    # ANDROID
    #--------------------------------------------------------------

    def load_android_avds(self):
        process = subprocess.Popen([self.android, "list", "avd", "-c"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        self.avds = result.split()

    def select_android_target(self, select):
        if select < 0:
            return
        target = self.targets[select]
        if (target == "emulator"):
            self.load_android_avds()
            self.show_quick_panel(self.avds, self.select_android_avd)
        elif(target == "dist-adhoc"):
            self.updateAndroidBuildInTiApp()
            self.run_titanium(['--build-only', "--output-dir", self.project_folder + self.outputDir])
        else:
            self.run_titanium(["--target", target])

    def select_android_avd(self, select):
        if select < 0:
            return
        self.run_titanium(["--avd-id", self.avds[select]])

    #--------------------------------------------------------------
    # IOS
    #--------------------------------------------------------------

    def select_ios_target(self, select):
        if select < 0:
            return
        self.target = self.targets[select]
        if self.target == "simulator":
            self.load_ios_info()
            self.simtype= []
            for simulator in self.simulators:
                self.simtype.append(simulator['id'])
            self.show_quick_panel(self.simtype, self.select_ios_simtype)
        elif self.target == "simulator auto":
            self.run_titanium([])
        else:
            self.families = ["iphone", "ipad", "universal"]
            self.show_quick_panel(self.families, self.select_ios_family)

    def select_ios_simtype(self, select):
        if select < 0:
            return
        deviceId =self.simtype[select]
        simulatorType = re.match('iphone|ipad', deviceId, re.IGNORECASE).group().lower()
        self.run_titanium(["--sim-type", simulatorType, "--device-id", deviceId])

    def select_ios_family(self, select):
        if select < 0:
            return
        self.family = self.families[select]
        if (self.certsDir is not "unknown"):
            print (self.certsDir)
            certsPath = os.path.join(self.project_folder, self.certsDir)
            if (self.target == "device"):
                certPath = os.path.join(certsPath, "development.mobileprovision")
            elif (self.target == "dist-appstore"):
                certPath = os.path.join(certsPath, "appstore.mobileprovision")
            else:
                certPath = os.path.join(certsPath, "distribution.mobileprovision")
            try:
                profile, teamname, teamid = self.getUUIDAndName(certPath)
                print (profile, teamname, teamid)
                self.copyProvisioningProfile(certPath, profile)
                self.build_ios_with_profile(teamname + " (" + teamid + ")", profile)
            except Exception: 
                self.handleError()
        else:
            self.load_ios_info()
            self.show_quick_panel(self.certs, self.select_ios_cert)

    def select_ios_cert(self, select):
        if select < 0:
            return
        self.cert = self.certs[select]
        self.show_quick_panel(self.profiles, self.select_ios_profile)

    def select_ios_profile(self, select):
        if select < 0:
            return
        name, profile = self.profiles[select]
        self.build_ios_with_profile(name, profile)

    def build_ios_with_profile(self, name, profile):
        options = ["--target", self.target, "--pp-uuid", profile, "--device-family", self.family]
        if self.target == "device":
            options.extend(["--developer-name", name])
        else:
            options.extend(["--distribution-name", name])

        if self.target == "dist-adhoc":
            self.updateIOsBuildInTiApp();
            options.extend(["--output-dir", self.project_folder + self.outputDir])
        self.run_titanium(options)

    def load_ios_info(self):
        process = subprocess.Popen( self.preCmd + ["info", "--types", "ios", "--log-level", "error", "--output", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        info = json.loads(result.decode('utf-8'))
        print (info)
        if "ios" in info:
            ios = info['ios'];
            if "certs" in ios:
                for target, c in list(ios["certs"].items()):
                    if target == "wwdr" or (target == "devNames" and self.target != "device") or (target == "distNames" and self.target == "device"):
                        continue
                    l = []
                    for cert in c:
                        l.append(cert)
                    self.certs = l
            if "provisioningProfiles" in ios:
                for target, p in list(ios["provisioningProfiles"].items()):
                    # TODO: figure out what to do with enterprise profiles
                    if (target == "development" and self.target == "device") or (target == "distribution" and self.target == "dist-appstore") or (target == "adhoc" and self.target == "dist-adhoc"):
                        l = []
                        for profile in p:
                            l.append([profile['name'], profile['uuid']])
                        self.profiles = l
            if "simulators" in ios:
                self.simulators = ios["simulators"]
                print (self.simulators)
        else:
            if "iosCerts" in info:
                for target, c in list(info["iosCerts"].items()):
                    if target == "wwdr" or (target == "devNames" and self.target != "device") or (target == "distNames" and self.target == "device"):
                        continue
                    l = []
                    for cert in c:
                        l.append(cert)
                    self.certs = l
            if "iOSProvisioningProfiles" in info:
                for target, p in list(info["iOSProvisioningProfiles"].items()):
                    # TODO: figure out what to do with enterprise profiles
                    if (target == "development" and self.target == "device") or (target == "distribution" and self.target == "dist-appstore") or (target == "adhoc" and self.target == "dist-adhoc"):
                        l = []
                        for profile in p:
                            l.append([profile['name'], profile['uuid']])
                        self.profiles = l
            self.simulators = None
            print (self.profiles)
            print (self.certs)
