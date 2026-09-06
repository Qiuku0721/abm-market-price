using System.Diagnostics;

namespace AbmCollectorApp;

/// <summary>adb 封装：设备列表 / 抓帧 / 点击滑动。数据链路仍走 USB。 </summary>
public class AdbClient
{
    public string AdbPath { get; }
    public string? Serial { get; set; }

    public AdbClient()
    {
        AdbPath = FindAdb()
            ?? throw new InvalidOperationException(
                "未找到 adb：请安装 platform-tools 或设置 ANDROID_HOME。");
    }

    public static string? FindAdb()
    {
        var env = Environment.GetEnvironmentVariable("ANDROID_HOME");
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var candidates = new List<string>();
        if (!string.IsNullOrEmpty(env)) candidates.Add(Path.Combine(env, "platform-tools", "adb.exe"));
        candidates.Add(Path.Combine(home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"));
        candidates.Add(@"D:\IDEA\adb\platform-tools\adb.exe");
        foreach (var c in candidates) if (File.Exists(c)) return c;

        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (var dir in pathVar.Split(';', StringSplitOptions.RemoveEmptyEntries))
        {
            try
            {
                var f = Path.Combine(dir.Trim('"'), "adb.exe");
                if (File.Exists(f)) return f;
            }
            catch { /* 忽略非法路径 */ }
        }
        return null;
    }

    private byte[] Exec(IEnumerable<string> args, int timeoutMs = 15000)
    {
        var psi = new ProcessStartInfo
        {
            FileName = AdbPath,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (var a in args) psi.ArgumentList.Add(a);
        using var p = Process.Start(psi) ?? throw new InvalidOperationException("adb 启动失败");
        var stdout = new MemoryStream();
        var task = p.StandardOutput.BaseStream.CopyToAsync(stdout);
        var stderr = p.StandardError.ReadToEndAsync();
        if (!p.WaitForExit(timeoutMs))
        {
            try { p.Kill(entireProcessTree: true); } catch { }
            throw new TimeoutException("adb 命令超时");
        }
        task.Wait(timeoutMs);
        if (p.ExitCode != 0)
        {
            var err = stderr.Result;
            throw new InvalidOperationException($"adb 失败({p.ExitCode}): {err[..Math.Min(200, err.Length)]}");
        }
        return stdout.ToArray();
    }

    private string[] Run(IEnumerable<string> args) =>
        System.Text.Encoding.UTF8.GetString(Exec(args)).Split('\n');

    /// <summary>在线设备序列号列表（状态为 device）。</summary>
    public List<string> Devices()
    {
        var list = new List<string>();
        foreach (var raw in Run(new[] { "devices" }))
        {
            var line = raw.Trim();
            if (line.EndsWith("\tdevice") || line.EndsWith(" device"))
            {
                list.Add(line.Split('\t', ' ')[0]);
            }
        }
        return list;
    }

    private string[] WithSerial(IEnumerable<string> args)
    {
        if (string.IsNullOrEmpty(Serial)) throw new InvalidOperationException("未选择设备");
        return new[] { "-s", Serial!, }.Concat(args).ToArray();
    }

    /// <summary>抓一帧全屏 PNG（经 USB）。</summary>
    public byte[] Screenshot() => Exec(WithSerial(new[] { "exec-out", "screencap", "-p" }), 20000);

    public void Tap(int x, int y) =>
        Run(WithSerial(new[] { "shell", "input", "tap", x.ToString(), y.ToString() }));

    public void Swipe(int x1, int y1, int x2, int y2, int ms) =>
        Run(WithSerial(new[] { "shell", "input", "swipe",
            x1.ToString(), y1.ToString(), x2.ToString(), y2.ToString(), ms.ToString() }));

    public void Back() => Run(WithSerial(new[] { "shell", "input", "keyevent", "4" }));
}
