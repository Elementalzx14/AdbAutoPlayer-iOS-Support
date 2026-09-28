using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

class Setup : Form {
    TextBox folder = new TextBox();
    TextBox status = new TextBox();
    Button install = new Button(), restore = new Button(), browse = new Button();
    bool busy;
    const string Release = "https://github.com/AdbAutoPlayer/AdbAutoPlayer/releases/tag/12.13.0";

    Setup() {
        Text = "AdbAutoPlayer iOS Support - 12.13.0 Setup";
        ClientSize = new Size(680, 430); StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        Font = new Font("Segoe UI", 10);
        var title = new Label { Text = "Add iOS support to AdbAutoPlayer 12.13.0", Left = 20, Top = 18, Width = 640, Height = 30, Font = new Font("Segoe UI", 15, FontStyle.Bold) };
        var info = new Label { Text = "Install the official Windows x64 12.13.0 app first, then close it.\r\nThis add-on includes its own Python runtime and preserves game settings.\r\nApple Devices is required for USB. iPad layouts are not yet validated.", Left = 20, Top = 58, Width = 640, Height = 85 };
        var link = new LinkLabel { Text = "Download official AdbAutoPlayer 12.13.0", Left = 20, Top = 146, Width = 430, Height = 25 };
        link.LinkClicked += delegate { Process.Start(Release); };
        folder.SetBounds(20, 183, 535, 28);
        folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AdbAutoPlayer");
        browse.Text = "Browse..."; browse.SetBounds(562, 182, 98, 30);
        browse.Click += delegate { using (var d = new FolderBrowserDialog()) { d.Description = "Select the folder containing adb-auto-player.exe"; d.SelectedPath = folder.Text; if (d.ShowDialog() == DialogResult.OK) folder.Text = d.SelectedPath; } };
        install.Text = "Install iOS Support"; install.SetBounds(20, 228, 205, 36);
        restore.Text = "Restore previous files"; restore.SetBounds(235, 228, 205, 36);
        install.Click += async delegate { await Execute("install"); };
        restore.Click += async delegate { await Execute("restore"); };
        status.SetBounds(20, 279, 640, 130); status.Multiline = true; status.ReadOnly = true; status.ScrollBars = ScrollBars.Vertical;
        status.Text = "Ready. Connect one unlocked, trusted iPhone after installation.\r\nTested with iPhone 17 Pro Max, iOS 27, English portrait AFK Journey.";
        Controls.AddRange(new Control[] { title, info, link, folder, browse, install, restore, status });
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy) e.Cancel = true; };
    }

    async Task Execute(string action) {
        busy = true; install.Enabled = restore.Enabled = browse.Enabled = folder.Enabled = false;
        status.Text = "Checking files and preparing the bundled runtime. Please wait...";
        string app = folder.Text;
        try {
            var result = await Task.Run(() => Run(app, action));
            status.Text = result.Item2;
            MessageBox.Show(this, result.Item2, result.Item1 == 0 ? "Finished" : "Setup could not complete", MessageBoxButtons.OK, result.Item1 == 0 ? MessageBoxIcon.Information : MessageBoxIcon.Error);
        } catch (Exception e) { status.Text = e.Message; }
        finally { busy = false; install.Enabled = restore.Enabled = browse.Enabled = folder.Enabled = true; }
    }

    static Tuple<int, string> Run(string app, string action) {
        string temp = Path.Combine(Path.GetTempPath(), "AdbAutoPlayer-iOS-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        try {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            using (var zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
                foreach (var entry in zip.Entries) {
                    string target = Path.GetFullPath(Path.Combine(temp, entry.FullName));
                    if (!target.StartsWith(temp + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new Exception("Invalid package path.");
                    if (entry.Name.Length == 0) { Directory.CreateDirectory(target); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    entry.ExtractToFile(target);
                }
            }
            var start = new ProcessStartInfo(Path.Combine(temp, "runtime", "Scripts", "python.exe"));
            start.Arguments = "-B \"" + Path.Combine(temp, "install.py") + "\" --app \"" + Path.GetFullPath(app).TrimEnd('\\') + "\" --action " + action;
            start.UseShellExecute = false; start.CreateNoWindow = true;
            start.RedirectStandardOutput = start.RedirectStandardError = true;
            start.EnvironmentVariables.Remove("PYTHONHOME"); start.EnvironmentVariables.Remove("PYTHONPATH");
            start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            using (var process = Process.Start(start)) {
                var stdout = process.StandardOutput.ReadToEndAsync();
                var stderr = process.StandardError.ReadToEndAsync();
                process.WaitForExit(); Task.WaitAll(stdout, stderr);
                return Tuple.Create(process.ExitCode, stdout.Result + stderr.Result);
            }
        } finally { try { Directory.Delete(temp, true); } catch { } }
    }

    [STAThread] static int Main(string[] args) {
        if (args.Length >= 2) {
            try {
                var result = Run(args[1], args[0].TrimStart('-'));
                if (args.Length > 2) File.WriteAllText(args[2], result.Item2);
                return result.Item1;
            } catch (Exception e) { if (args.Length > 2) File.WriteAllText(args[2], e.ToString()); return 1; }
        }
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new Setup()); return 0;
    }
}
