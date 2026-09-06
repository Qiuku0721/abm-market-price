using System.Text.Json;
using System.Text.Json.Serialization;

namespace AbmCollectorApp;

/// <summary>采集配置模型：键名与 pc/collector/config.json（python 端）一一对应。</summary>
public class CollectorConfig
{
    [JsonPropertyName("calibers")] public List<string> Calibers { get; set; } = new()
    {
        "7.62x39毫米", "7.62x54毫米", "5.56x45毫米", "9x19毫米",
        "7.62x51毫米", "5.7x28毫米", "9x39毫米", "5.45x39毫米", "12.7x99毫米",
        ".44口径", ".45口径", "7.62x25毫米", ".338口径", "5.8x42毫米",
    };
    [JsonPropertyName("interval_sec")] public int IntervalSec { get; set; } = 60;
    [JsonPropertyName("nav_taps")] public List<double[]> NavTaps { get; set; } = new();
    [JsonPropertyName("left_panel")] public PanelCfg LeftPanel { get; set; } = new(0.12, 0.60, 0.46, 300);
    [JsonPropertyName("grid_panel")] public PanelCfg GridPanel { get; set; } = new(0.62, 0.72, 0.30, 400);
    [JsonPropertyName("grid_back_to_top_swipes")] public int GridBackToTopSwipes { get; set; } = 4;
    [JsonPropertyName("grid_scroll_after_caliber")] public bool GridScrollAfterCaliber { get; set; } = true;
    [JsonPropertyName("price_below_row_px")] public int PriceBelowRowPx { get; set; } = 120;
    [JsonPropertyName("max_left_scrolls")] public int MaxLeftScrolls { get; set; } = 8;
    [JsonPropertyName("scroll")] public ScrollCfg Scroll { get; set; } = new();
    [JsonPropertyName("top_swipes")] public int TopSwipes { get; set; } = 6;
    [JsonPropertyName("price_zone_left_x")] public double PriceZoneLeftX { get; set; } = 0.52;
    [JsonPropertyName("row_pad_px")] public int RowPadPx { get; set; } = 22;
    [JsonPropertyName("max_scrolls")] public int MaxScrolls { get; set; } = 12;
    [JsonPropertyName("stagnant_limit")] public int StagnantLimit { get; set; } = 2;
    [JsonPropertyName("action_delay_ms")] public int ActionDelayMs { get; set; } = 500;
    [JsonPropertyName("debug_save")] public int DebugSave { get; set; } = 1;
    [JsonPropertyName("save_snapshots")] public bool SaveSnapshots { get; set; } = true;
}

public class PanelCfg
{
    [JsonPropertyName("x")] public double X { get; set; }
    [JsonPropertyName("from_y")] public double FromY { get; set; }
    [JsonPropertyName("to_y")] public double ToY { get; set; }
    [JsonPropertyName("duration_ms")] public int DurationMs { get; set; }

    public PanelCfg() : this(0.5, 0.72, 0.30, 350) { }

    public PanelCfg(double x, double fromY, double toY, int durationMs)
    {
        X = x; FromY = fromY; ToY = toY; DurationMs = durationMs;
    }
}

public class ScrollCfg
{
    [JsonPropertyName("from_y")] public double FromY { get; set; } = 0.72;
    [JsonPropertyName("to_y")] public double ToY { get; set; } = 0.30;
    [JsonPropertyName("x")] public double X { get; set; } = 0.5;
    [JsonPropertyName("duration_ms")] public int DurationMs { get; set; } = 400;
}

/// <summary>读写 pc/collector/config.json（python 采集器直接读取该文件）。</summary>
public static class ConfigService
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    /// <summary>从可执行文件位置向上查找仓库 pc/collector/config.json。</summary>
    public static string? FindDefaultPath()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        for (var d = dir; d != null; d = d.Parent)
        {
            var p = Path.Combine(d.FullName, "pc", "collector", "config.json");
            if (File.Exists(p)) return p;
        }
        return null;
    }

    public static CollectorConfig Load(string path)
    {
        if (!File.Exists(path))
        {
            var cfg = new CollectorConfig();
            Save(path, cfg);
            return cfg;
        }
        var json = File.ReadAllText(path);
        var loaded = JsonSerializer.Deserialize<CollectorConfig>(json, JsonOpts);
        return loaded ?? new CollectorConfig();
    }

    public static void Save(string path, CollectorConfig cfg)
    {
        var dir = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
        File.WriteAllText(path, JsonSerializer.Serialize(cfg, JsonOpts));
    }
}
