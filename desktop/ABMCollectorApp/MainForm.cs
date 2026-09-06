using System.Diagnostics;

namespace AbmCollectorApp;

/// <summary>
/// ABM 桌面采集控制端：实时预览手机画面、鼠标点选「每轮导航点击位置」、
/// 调节采集频率与子弹清单，并一键启动/停止 python 采集控制器（run_collector.py）。
/// 识别与入库仍由 python 完成，本程序只写 pc/collector/config.json。
/// </summary>
public class MainForm : Form
{
    private AdbClient? _adb;
    private CollectorConfig _cfg = new();
    private string _configPath = "";
    private Process? _python;
    private bool _busy;

    // 预览
    private readonly PictureBox _pb = new();
    private readonly CheckBox _cbLive = new() { Text = "实时预览(1s)", AutoSize = true };
    private readonly System.Windows.Forms.Timer _liveTimer = new() { Interval = 1000 };
    private int _imgW, _imgH;      // 预览显示（缩略）图尺寸
    private int _fullW, _fullH;    // 手机实际截图尺寸（用于试点点击像素换算）

    // 设备
    private readonly ComboBox _cbDevices = new() { DropDownStyle = ComboBoxStyle.DropDownList };
    private readonly Label _lblAdb = new() { AutoSize = true, ForeColor = Color.Gray };

    // 设置
    private readonly ListBox _listNav = new();
    private readonly NumericUpDown _numInterval = new() { Minimum = 5, Maximum = 86400, Value = 60 };
    private readonly TextBox _txtConfigPath = new();
    private readonly Label _lblPy = new() { AutoSize = true, ForeColor = Color.SteelBlue };
    private readonly TextBox _txtLog = new()
    {
        Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical,
        Dock = DockStyle.Fill, BackColor = Color.FromArgb(20, 18, 28),
        ForeColor = Color.FromArgb(236, 234, 244),
    };

    public MainForm()
    {
        Text = "ABM 桌面采集控制端";
        Width = 1280; Height = 800;
        MinimumSize = new Size(1100, 700);
        StartPosition = FormStartPosition.CenterScreen;
        _cfg = new CollectorConfig();

        BuildUi();
        TryInitAdb();
        LoadConfigIntoUi();
        _liveTimer.Tick += async (_, _) => await GrabFrameAsync();
        _cbLive.CheckedChanged += (_, _) =>
        {
            if (_cbLive.Checked) _liveTimer.Start(); else _liveTimer.Stop();
        };
        _cbDevices.SelectedIndexChanged += (_, _) =>
        {
            if (_adb is null) return;
            _adb.Serial = _cbDevices.SelectedItem?.ToString();
            _ = GrabFrameAsync();
        };
    }

    // ---------------- UI 搭建 ----------------
    private void BuildUi()
    {
        // 顶部：设备栏
        var top = new Panel { Dock = DockStyle.Top, Height = 38, Padding = new Padding(8, 6, 8, 0) };
        top.Controls.Add(new Label { Text = "设备:", AutoSize = true, Location = new Point(10, 9) });
        _cbDevices.Location = new Point(60, 6); _cbDevices.Width = 220; top.Controls.Add(_cbDevices);
        var btnRefresh = new Button { Text = "刷新设备", Location = new Point(290, 5), Width = 90 };
        btnRefresh.Click += (_, _) => TryInitAdb();
        top.Controls.Add(btnRefresh);
        _lblAdb.Location = new Point(395, 10); _lblAdb.MaximumSize = new Size(640, 20);
        top.Controls.Add(_lblAdb);
        Controls.Add(top);

        // 底部：日志
        var logPanel = new Panel { Dock = DockStyle.Bottom, Height = 150, Padding = new Padding(6) };
        logPanel.Controls.Add(_txtLog);
        Controls.Add(logPanel);

        // 中部左右分栏
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Orientation = Orientation.Vertical,
        };

        // 左：预览
        var left = new Panel { Dock = DockStyle.Fill, Padding = new Padding(6) };
        var tool = new Panel { Dock = DockStyle.Top, Height = 34 };
        var btnGrab = new Button { Text = "抓一帧", Width = 90 };
        btnGrab.Click += async (_, _) => await GrabFrameAsync();
        tool.Controls.Add(btnGrab);
        _cbLive.Location = new Point(100, 8); tool.Controls.Add(_cbLive);
        var hint = new Label
        {
            Text = "左键点画面 = 添加一个每轮点击点（红圈序号）",
            AutoSize = true, Location = new Point(240, 10), ForeColor = Color.Gray,
        };
        tool.Controls.Add(hint);
        left.Controls.Add(tool);
        _pb.Dock = DockStyle.Fill;
        _pb.SizeMode = PictureBoxSizeMode.Zoom;
        _pb.BackColor = Color.FromArgb(24, 22, 34);
        _pb.MouseClick += Pb_MouseClick;
        _pb.Paint += Pb_Paint;
        left.Controls.Add(_pb);
        split.Panel1.Controls.Add(left);

        // 右：设置（TableLayout 自适应宽，避免错位）
        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 1,
            AutoScroll = true,
            Padding = new Padding(2),
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        table.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        void AddRow(Control c)
        {
            c.Dock = DockStyle.Top;
            c.Margin = new Padding(0, 2, 0, 2);
            table.Controls.Add(c, 0, table.RowCount);
            table.RowCount += 1;
        }
        void AddLabel(string s) => AddRow(new Label { Text = s, AutoSize = true, Dock = DockStyle.Top });

        AddLabel("每轮导航点击点（红点/列表；顺序=执行顺序）：");
        _listNav.Height = 108; _listNav.IntegralHeight = false; AddRow(_listNav);
        var btns = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Top };
        var bDel = new Button { Text = "删除选中", Width = 92 };
        bDel.Click += (_, _) => { if (_listNav.SelectedIndex >= 0) { _listNav.Items.RemoveAt(_listNav.SelectedIndex); _pb.Invalidate(); } };
        var bTest = new Button { Text = "试点最后", Width = 92 };
        bTest.Click += (_, _) => TestTapLast();
        var bClear = new Button { Text = "清空", Width = 70 };
        bClear.Click += (_, _) => { _listNav.Items.Clear(); _pb.Invalidate(); };
        btns.Controls.AddRange(new Control[] { bDel, bTest, bClear });
        AddRow(btns);

        AddLabel("采集频率（秒，5~86400）：");
        _numInterval.Width = 120; AddRow(_numInterval);

        var bSave = new Button { Text = "保存配置 → config.json", Height = 30, Dock = DockStyle.Top };
        bSave.Click += (_, _) => SaveConfigToFile();
        AddRow(bSave);

        var bReset = new Button
        {
            Text = "♻ 一键重置（清空全部记录/日志/历史）",
            Height = 32, Dock = DockStyle.Top,
            BackColor = Color.IndianRed, ForeColor = Color.White,
        };
        bReset.Click += (_, _) => ResetAllData();
        AddRow(bReset);

        AddLabel("采集控制（启动 python run_collector.py）：");
        var pyBtns = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Top };
        var bStart = new Button { Text = "▶ 启动采集", Width = 130 };
        bStart.Click += (_, _) => StartCollector();
        var bStop = new Button { Text = "■ 停止", Width = 100, BackColor = Color.IndianRed };
        bStop.Click += (_, _) => StopCollector();
        pyBtns.Controls.AddRange(new Control[] { bStart, bStop });
        AddRow(pyBtns);
        AddRow(_lblPy);

        AddLabel("config.json 路径：");
        _txtConfigPath.Height = 26; AddRow(_txtConfigPath);
        var bBrowse = new Button { Text = "浏览…", Width = 90, Dock = DockStyle.Left };
        bBrowse.Click += (_, _) =>
        {
            using var dlg = new OpenFileDialog { Filter = "config.json|config.json", FileName = _txtConfigPath.Text };
            if (dlg.ShowDialog(this) == DialogResult.OK) { _txtConfigPath.Text = dlg.FileName; }
        };
        AddRow(bBrowse);

        var right = new Panel { Dock = DockStyle.Fill, Padding = new Padding(4) };
        right.Controls.Add(table);
        split.Panel2.Controls.Add(right);
        Controls.Add(split);

        // 窗体布局完成后再设置分隔条位置（避免构造期 MinSize 校验冲突）
        var splitRef = split;
        Load += (_, _) =>
        {
            try { splitRef.SplitterDistance = (int)(ClientSize.Width * 0.62); } catch { }
        };
    }

    // ---------------- 设备 ----------------
    private void TryInitAdb()
    {
        try
        {
            _adb = new AdbClient();
            _lblAdb.Text = "adb: " + _adb.AdbPath;
            RefreshDevices();
        }
        catch (Exception ex)
        {
            _lblAdb.Text = ex.Message;
            Log("adb 不可用：" + ex.Message);
        }
    }

    private void RefreshDevices()
    {
        if (_adb is null) return;
        try
        {
            var devices = _adb.Devices();
            _cbDevices.Items.Clear();
            foreach (var d in devices) _cbDevices.Items.Add(d);
            if (devices.Count > 0) { _cbDevices.SelectedIndex = 0; }
            else { Log("未检测到在线设备：请插 USB 并允许调试授权"); _pb.Invalidate(); }
        }
        catch (Exception ex) { Log("设备列表失败：" + ex.Message); }
    }

    // ---------------- 预览与标定 ----------------
    private async Task GrabFrameAsync()
    {
        if (_adb is null || _busy) return;
        var serial = _cbDevices.SelectedItem?.ToString() ?? _adb.Serial;
        if (string.IsNullOrEmpty(serial)) return;
        _busy = true;
        try
        {
            _adb.Serial = serial;
            var png = await Task.Run(_adb.Screenshot);
            using var ms = new MemoryStream(png);
            var bmp = new Bitmap(ms);
            var origW = bmp.Width; var origH = bmp.Height;
            // 预览帧先缩略（≤1280px 宽），大幅降低每帧渲染/解码的 CPU
            var thumb = bmp.Width > 1280
                ? new Bitmap(bmp, 1280, (int)(bmp.Height * 1280.0 / bmp.Width))
                : bmp;
            if (!ReferenceEquals(thumb, bmp)) bmp.Dispose();
            var old = _pb.Image;
            _pb.Image = thumb;
            old?.Dispose();
            _imgW = thumb.Width; _imgH = thumb.Height; _fullW = origW; _fullH = origH;
            _pb.Invalidate();
        }
        catch (Exception ex) { Log("抓帧失败：" + ex.Message); }
        finally { _busy = false; }
    }

    private void Pb_MouseClick(object? sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left || _imgW == 0 || _imgH == 0) return;
        if (!TryClientToImage(e.Location, out int ix, out int iy)) return;
        double nx = Math.Round(ix * 1.0 / _imgW, 3);
        double ny = Math.Round(iy * 1.0 / _imgH, 3);
        _listNav.Items.Add($"{nx:F3}, {ny:F3}");
        _pb.Invalidate();
        Log($"添加点击点 #{_listNav.Items.Count}: 归一化({nx:F3},{ny:F3}) = 像素({ix},{iy})");
    }

    private void TestTapLast()
    {
        if (_adb is null || _imgW == 0 || _listNav.Items.Count == 0) return;
        var p = ParseNav(_listNav.Items[_listNav.Items.Count - 1].ToString());
        if (p is null) return;
        try
        {
            _adb.Serial = _cbDevices.SelectedItem?.ToString() ?? _adb.Serial;
            _adb.Tap((int)(p.Value.Item1 * _fullW), (int)(p.Value.Item2 * _fullH));
            Log($"已试点 ({p.Value.Item1:F3},{p.Value.Item2:F3})");
        }
        catch (Exception ex) { Log("试点失败：" + ex.Message); }
    }

    private void Pb_Paint(object? sender, PaintEventArgs e)
    {
        if (_imgW == 0 || _imgH == 0)
        {
            using var f = new Font("微软雅黑", 12f);
            e.Graphics.DrawString("未获取画面：请在上方选设备后点「抓一帧」，并确认手机已插线/允许USB调试",
                f, Brushes.Gray, 20, 20);
            return;
        }
        var box = ImageDisplayRect();
        var scale = box.Width * 1.0 / _imgW;
        for (int i = 0; i < _listNav.Items.Count; i++)
        {
            var p = ParseNav(_listNav.Items[i].ToString());
            if (p is null) continue;
            var cx = (float)(box.X + p.Value.Item1 * _imgW * scale);
            var cy = (float)(box.Y + p.Value.Item2 * _imgH * scale);
            using var pen = new Pen(Color.Red, 3f);
            e.Graphics.DrawEllipse(pen, cx - 10, cy - 10, 20, 20);
            using var font = new Font("Arial", 9f, FontStyle.Bold);
            e.Graphics.DrawString((i + 1).ToString(), font, Brushes.Yellow, cx + 8, cy - 12);
        }
    }

    private Rectangle ImageDisplayRect()
    {
        if (_pb.Image is null) return Rectangle.Empty;
        var cw = _pb.ClientSize.Width; var ch = _pb.ClientSize.Height;
        var scale = Math.Min(cw * 1.0 / _imgW, ch * 1.0 / _imgH);
        var w = (int)(_imgW * scale); var h = (int)(_imgH * scale);
        return new Rectangle((cw - w) / 2, (ch - h) / 2, w, h);
    }

    private bool TryClientToImage(Point c, out int ix, out int iy)
    {
        ix = iy = 0;
        var box = ImageDisplayRect();
        if (box.IsEmpty || box.Width == 0) return false;
        var scale = box.Width * 1.0 / _imgW;
        ix = (int)Math.Clamp((c.X - box.X) / scale, 0, _imgW - 1);
        iy = (int)Math.Clamp((c.Y - box.Y) / scale, 0, _imgH - 1);
        return true;
    }

    private static (double, double)? ParseNav(string? s)
    {
        if (string.IsNullOrWhiteSpace(s)) return null;
        var parts = s.Split(',', '，');
        if (parts.Length < 2) return null;
        if (double.TryParse(parts[0].Trim(), out var x) && double.TryParse(parts[1].Trim(), out var y))
            return (x, y);
        return null;
    }

    // ---------------- 配置读写 ----------------
    private void LoadConfigIntoUi()
    {
        // 发行版：优先用程序同目录的 config.json；开发模式再找仓库 pc/collector/config.json
        var local = Path.Combine(AppContext.BaseDirectory, "config.json");
        if (File.Exists(local))
        {
            _configPath = local;
            try { _cfg = ConfigService.Load(_configPath); }
            catch (Exception ex) { Log("读取配置失败（将用默认）：" + ex.Message); }
        }
        else
        {
            _configPath = ConfigService.FindDefaultPath() ?? "";
            if (string.IsNullOrEmpty(_configPath))
            {
                _configPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                    "ABM", "pc", "collector", "config.json");
                Log("未找到仓库 config.json，将使用：" + _configPath);
            }
            else
            {
                try { _cfg = ConfigService.Load(_configPath); }
                catch (Exception ex) { Log("读取配置失败（将用默认）：" + ex.Message); }
            }
        }
        _txtConfigPath.Text = _configPath;
        _numInterval.Value = Math.Clamp(_cfg.IntervalSec, 5, 86400);
        _listNav.Items.Clear();
        foreach (var t in _cfg.NavTaps)
            if (t.Length >= 2) _listNav.Items.Add($"{t[0]:F3}, {t[1]:F3}");
    }

    private void SaveConfigToFile()
    {
        _cfg.IntervalSec = (int)_numInterval.Value;
        _cfg.NavTaps = _listNav.Items.Cast<string>()
            .Select(ParseNav)
            .Where(p => p.HasValue)
            .Select(p => new[] { p!.Value.Item1, p.Value.Item2 }).ToList();
        try
        {
            ConfigService.Save(_configPath, _cfg);
            Log($"已保存配置：{_configPath}（间隔 {_cfg.IntervalSec}s，点击 {_cfg.NavTaps.Count} 个，口径 {_cfg.Calibers.Count} 个）");
        }
        catch (Exception ex) { Log("保存失败：" + ex.Message); }
    }

    // ---------------- 采集进程 ----------------
    private void StartCollector()
    {
        if (_python is { HasExited: false }) { Log("采集已在运行"); return; }
        SaveConfigToFile();
        var abmExe = Path.Combine(AppContext.BaseDirectory, "abm.exe");
        ProcessStartInfo psi;
        if (File.Exists(abmExe))
        {
            // 发行版：调用同目录 abm.exe collect，并把数据目录指向发行目录 data/
            var dir = AppContext.BaseDirectory;
            psi = NewPyPsi(abmExe);
            psi.ArgumentList.Add("collect");
            psi.ArgumentList.Add("--config");
            psi.ArgumentList.Add(_configPath);
            psi.EnvironmentVariables["ABM_DB"] = Path.Combine(dir, "data", "abm.db");
            psi.EnvironmentVariables["ABM_SNAPSHOTS_DIR"] = Path.Combine(dir, "data", "snapshots");
            psi.EnvironmentVariables["ABM_STATIC_DIR"] = Path.Combine(dir, "data");
            psi.EnvironmentVariables["ABM_WEB_STATIC"] = Path.Combine(dir, "web", "static");
        }
        else
        {
            var repo = FindRepoRoot();
            if (repo is null) { Log("无法定位仓库根目录，请确认程序放置在 ABM Project 内"); return; }
            var py = Path.Combine(repo, "pc", ".venv", "Scripts", "python.exe");
            var script = Path.Combine(repo, "pc", "run_collector.py");
            if (!File.Exists(py)) { Log("未找到 pc\\.venv\\Scripts\\python.exe：请先运行 pc\\scripts\\start.bat 完成环境安装"); return; }
            if (!File.Exists(script)) { Log("未找到 run_collector.py：" + script); return; }
            psi = NewPyPsi(py);
            psi.ArgumentList.Add(script);
            psi.ArgumentList.Add("--config");
            psi.ArgumentList.Add(_configPath);
        }

        _python = Process.Start(psi);
        if (_python is null) { Log("启动失败"); return; }
        _python.OutputDataReceived += (_, e) => { if (!string.IsNullOrEmpty(e.Data)) Log("[采集] " + e.Data); };
        _python.ErrorDataReceived += (_, e) => { if (!string.IsNullOrEmpty(e.Data)) Log("[采集!] " + e.Data); };
        _python.BeginOutputReadLine();
        _python.BeginErrorReadLine();
        _lblPy.Text = "状态：采集中（采集进程运行中）";
        Log("已启动采集（数据可到 http://127.0.0.1:8600 查看）");
    }

    private static ProcessStartInfo NewPyPsi(string fileName) => new()
    {
        FileName = fileName,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
        CreateNoWindow = true,
        StandardOutputEncoding = System.Text.Encoding.UTF8,
        StandardErrorEncoding = System.Text.Encoding.UTF8,
    };

    private void ResetAllData()
    {
        if (MessageBox.Show(
            "确定要一键重置吗？\n将删除所有历史记录、价格表、日志与快照，且不可恢复。",
            "一键重置", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
            return;

        var baseDir = AppContext.BaseDirectory;
        var db = Path.Combine(baseDir, "data", "abm.db");
        var snaps = Path.Combine(baseDir, "data", "snapshots");
        var abm = Path.Combine(baseDir, "abm.exe");

        string exe; var args = new List<string>();
        if (File.Exists(abm))
        {
            exe = abm; args.Add("reset");
        }
        else
        {
            var repo = FindRepoRoot();
            if (repo is null) { Log("无法定位程序/仓库目录，无法重置"); return; }
            exe = Path.Combine(repo, "pc", ".venv", "Scripts", "python.exe");
            args.Add(Path.Combine(repo, "pc", "entry.py"));
            args.Add("reset");
            db = Path.Combine(repo, "pc", "data", "abm.db");
            snaps = Path.Combine(repo, "pc", "static", "snapshots");
        }

        if (File.Exists(db)) { args.Add("--db"); args.Add(db); }
        if (Directory.Exists(snaps)) { args.Add("--snapshots"); args.Add(snaps); }
        var logF = Path.Combine(baseDir, "collector.log");
        if (File.Exists(logF)) { args.Add("--logs"); args.Add(logF); }
        if (args.Count <= 1) { Log("当前没有可清理的数据"); return; }

        try
        {
            var psi = new ProcessStartInfo { FileName = exe, UseShellExecute = false, CreateNoWindow = true };
            foreach (var a in args) psi.ArgumentList.Add(a);
            using var p = Process.Start(psi);
            p?.WaitForExit(120000);
            Log("已一键重置：清空了历史记录、价格表、日志与快照");
        }
        catch (Exception ex) { Log("重置失败：" + ex.Message); }
    }

    private void StopCollector()
    {
        if (_python is null || _python.HasExited) { Log("采集未在运行"); _lblPy.Text = "状态：未运行"; return; }
        try { _python.Kill(entireProcessTree: true); } catch { }
        _python.Dispose(); _python = null;
        _lblPy.Text = "状态：已停止";
        Log("已停止采集");
    }

    private string? FindRepoRoot()
    {
        var dir = new DirectoryInfo(_configPath);
        for (var d = dir.Parent; d != null; d = d.Parent)
            if (File.Exists(Path.Combine(d.FullName, "pc", "run_collector.py"))) return d.FullName;
        return null;
    }

    private void Log(string msg)
    {
        if (IsDisposed) return;
        if (InvokeRequired)
        {
            try { BeginInvoke(() => AppendLog(msg)); } catch { }
        }
        else AppendLog(msg);
    }

    private void AppendLog(string msg)
    {
        var line = $"[{DateTime.Now:HH:mm:ss}] {msg}{Environment.NewLine}";
        _txtLog.AppendText(line);
        if (_txtLog.TextLength > 60_000) _txtLog.Text = _txtLog.Text[^40_000..];
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        StopCollector();
        _liveTimer.Stop();
        base.OnFormClosed(e);
    }
}
