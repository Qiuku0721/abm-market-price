using System.Diagnostics;
using System.Text.RegularExpressions;

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

    /// <summary>adb 命令（可带 stdin 输入，用于 pair）。</summary>
    private string RunWithInput(IEnumerable<string> args, string? input)
    {
        var psi = new ProcessStartInfo
        {
            FileName = AdbPath,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (var a in args) psi.ArgumentList.Add(a);
        using var p = Process.Start(psi) ?? throw new InvalidOperationException("adb 启动失败");
        if (input != null) p.StandardInput.Write(input + "\n");
        p.StandardInput.Close();
        var outp = p.StandardOutput.ReadToEnd();
        var err = p.StandardError.ReadToEnd();
        p.WaitForExit(20000);
        return String.IsNullOrEmpty(outp) ? err : outp;
    }

    /// <summary>自动发现局域网无线调试设备（adb mdns services）。返回 "名称 | ip:端口" 列表。</summary>
    public List<string> MdnsServices()
    {
        var list = new List<string>();
        foreach (var raw in Run(new[] { "mdns", "services" }))
        {
            var s = raw.Trim();
            if (s.Length == 0 || s.StartsWith("Name") || s.StartsWith("List of") || s.StartsWith("mdns daemon")) continue;
            var cols = Regex.Split(s, @"\s{2,}");
            if (cols.Length >= 4 && int.TryParse(cols[3], out _))
                list.Add($"{cols[0]} | {cols[2]}:{cols[3]}");
        }
        return list;
    }

    /// <summary>无线连接：可选首次配对（pair 端口+码），再 connect。</summary>
    public void WifiConnect(string host, int port, int? pairPort, string? pairCode)
    {
        if (pairPort is > 0 && !string.IsNullOrWhiteSpace(pairCode))
            RunWithInput(new[] { "pair", $"{host}:{pairPort}" }, pairCode);
        Run(new[] { "connect", $"{host}:{port}" });
    }

    public void WifiDisconnect(string addr) => Run(new[] { "disconnect", addr });

    /// <summary>设备状态：wireless（含 ':'）=无线 adb 设备，usb=本地设备。</summary>
    public Dictionary<string, List<string>> DeviceStatus()
    {
        var ids = Devices();
        return new Dictionary<string, List<string>>
        {
            ["wireless"] = ids.Where(a => a.Contains(":")).ToList(),
            ["usb"] = ids.Where(a => !a.Contains(":")).ToList(),
        };
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
