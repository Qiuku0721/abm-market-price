using System.Windows.Forms;

namespace AbmCollectorApp;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        try
        {
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += (_, e) => WriteCrash("ThreadException", e.Exception);
            AppDomain.CurrentDomain.UnhandledException += (_, e) => WriteCrash("Unhandled", e.ExceptionObject as Exception);
            ApplicationConfiguration.Initialize();
            Application.Run(new MainForm());
        }
        catch (Exception ex)
        {
            WriteCrash("Main", ex);
            throw;
        }
    }

    private static void WriteCrash(string kind, Exception? ex)
    {
        try
        {
            var path = Path.Combine(AppContext.BaseDirectory, "crash.log");
            File.AppendAllText(path, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {kind}: {ex}{Environment.NewLine}{Environment.NewLine}");
        }
        catch { /* 记录失败不影响 */ }
    }
}
