import sublime_plugin
import json
import subprocess


class TitaniumCommand(sublime_plugin.WindowCommand):

    def run(self, *args, **kwargs):
        self.platforms = ["android", "ios", "mobileweb"]
        self.window.show_quick_panel(self.platforms, self.select_platform)

    def select_platform(self, select):
        if select < 0:
            return
        self.platform = self.platforms[select]
        if self.platform == "ios":
            self.targets = ["simulator", "device", "dist-appstore", "dist-adhoc"]
            self.window.show_quick_panel(self.targets, self.select_ios_target)
        elif self.platform == "android":
            self.targets = ["emulator", "device", "dist-appstore", "dist-adhoc"]
            self.window.show_quick_panel(self.targets, self.select_android_target)
        else:
            self.targets = ["development", "production"]
            self.window.show_quick_panel(self.targets, self.select_mobileweb_target)

    def run_titanium(self, options=[]):
        folder = self.window.folders()[0]  # base project folder
        cmd = ["titanium", "build", "--project-dir", folder, "--no-colors", "--platform", self.platform]
        cmd.extend(options)
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
        process = subprocess.Popen(["android", "list", "avd", "-c"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        self.avds = result.split()

    def select_android_target(self, select):
        if select < 0:
            return
        target = self.targets[select]
        if (target == "emulator"):
            self.load_android_avds()
            self.window.show_quick_panel(self.avds, self.select_android_avd)
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
            self.simtype = ["iphone", "ipad"]
            self.window.show_quick_panel(self.simtype, self.select_ios_simtype)
        else:
            self.families = ["iphone", "ipad", "universal"]
            self.window.show_quick_panel(self.families, self.select_ios_family)

    def select_ios_simtype(self, select):
        if select < 0:
            return
        self.run_titanium(["--sim-type", self.simtype[select]])

    def select_ios_family(self, select):
        if select < 0:
            return
        self.family = self.families[select]
        self.load_ios_info()
        self.window.show_quick_panel(self.certs, self.select_ios_cert)

    def select_ios_cert(self, select):
        if select < 0:
            return
        self.cert = self.certs[select]
        self.window.show_quick_panel(self.profiles, self.select_ios_profile)

    def select_ios_profile(self, select):
        if select < 0:
            return
        name, profile = self.profiles[select]
        options = ["--target", self.target, "--pp-uuid", profile, "--device-family", self.family]
        if self.target == "device":
            options.extend(["--developer-name", self.cert])
        else:
            options.extend(["--distribution-name", self.cert])
        self.run_titanium(options)

    def load_ios_info(self):
        process = subprocess.Popen(["titanium", "info", "--types", "ios", "--output", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        info = json.loads(result)
        for name, obj in info.items():
            if name == "iosCerts":
                for target, c in obj.items():
                    if target == "wwdr" or (target == "devNames" and self.target != "device") or (target == "distNames" and self.target == "device"):
                        continue
                    l = []
                    for cert in c:
                        l.append(cert)
                    self.certs = l
            elif name == "iOSProvisioningProfiles":
                for target, p in obj.items():
                    # TODO: figure out what to do with enterprise profiles
                    if (target == "development" and self.target == "device") or (target == "distribution" and self.target == "dist-appstore") or (target == "adhoc" and self.target == "dist-adhoc"):
                        l = []
                        for profile in p:
                            l.append([profile['name'], profile['uuid']])
                        self.profiles = l