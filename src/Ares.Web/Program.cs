using Ares.Web;
using Ares.Web.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Logging.AddConsole();

builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// Toggle between live FastAPI client and local mock via appsettings.json
var useMock = builder.Configuration.GetValue<bool>("Ares:UseMock", defaultValue: false);
if (useMock)
{
    builder.Services.AddSingleton<IAresApiClient, MockAresApiClient>();
}
else
{
    var baseUrl = builder.Configuration["Ares:ApiBaseUrl"] ?? "http://localhost:8000";
    builder.Services.AddHttpClient<IAresApiClient, HttpAresApiClient>(c =>
    {
        c.BaseAddress = new Uri(baseUrl);
        c.Timeout = TimeSpan.FromSeconds(120); // evaluations can take up to 2 min
    });
}

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseAntiforgery();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
