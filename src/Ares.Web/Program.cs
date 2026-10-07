using Ares.Web;
using Ares.Web.Services;
using Microsoft.AspNetCore.DataProtection;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Logging.AddConsole();

// This unauthenticated prototype has no durable protected state. Avoid persisting
// development keys to a user profile; production authentication will replace this.
builder.Services.AddSingleton<IDataProtectionProvider, EphemeralDataProtectionProvider>();

builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents(options =>
    {
        options.DetailedErrors = builder.Environment.IsDevelopment();
    })
    .AddHubOptions(options =>
    {
        // Limit SignalR payload message size to 128KB to prevent buffer exhaustion DoS
        options.MaximumReceiveMessageSize = 128 * 1024;
    });

builder.Services.AddSingleton<MockQdrantCorpusService>();
builder.Services.AddScoped<MockAresApiClient>();

var useMock = builder.Configuration.GetValue<bool>("Ares:UseMock", defaultValue: false);
var baseUrl = builder.Configuration["Ares:ApiBaseUrl"] ?? "http://localhost:8000";
var apiKey = builder.Configuration["Ares:ApiKey"] ?? "ares-dev-secret-key-42";

if (useMock)
{
    builder.Services.AddScoped<IAresApiClient>(provider => provider.GetRequiredService<MockAresApiClient>());
    builder.Services.AddSingleton<IQdrantCorpusService>(provider => provider.GetRequiredService<MockQdrantCorpusService>());
}
else
{
    builder.Services.AddHttpClient<FastApiAresApiClient>(client =>
    {
        client.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/");
        client.Timeout = TimeSpan.FromSeconds(120);
        client.DefaultRequestHeaders.Add("X-Ares-User-Email", builder.Configuration["Ares:DevelopmentUserEmail"] ?? "developer@local");
        client.DefaultRequestHeaders.Add("X-Ares-Api-Key", apiKey);
    });
    builder.Services.AddScoped<IAresApiClient>(provider => provider.GetRequiredService<FastApiAresApiClient>());

    builder.Services.AddHttpClient<RealQdrantCorpusService>(client =>
    {
        client.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/");
        client.Timeout = TimeSpan.FromSeconds(30);
        client.DefaultRequestHeaders.Add("X-Ares-Api-Key", apiKey);
    });
    builder.Services.AddScoped<IQdrantCorpusService>(provider => provider.GetRequiredService<RealQdrantCorpusService>());
}

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

// Security Headers Middleware (Clickjacking, MIME-sniffing, XSS defense-in-depth, CSP)
app.Use(async (context, next) =>
{
    context.Response.Headers.Append("X-Frame-Options", "DENY");
    context.Response.Headers.Append("X-Content-Type-Options", "nosniff");
    context.Response.Headers.Append("Referrer-Policy", "strict-origin-when-cross-origin");
    context.Response.Headers.Append("Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()");
    context.Response.Headers.Append("Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss: http://localhost:8000 https://*.qdrant.io; img-src 'self' data: https:; font-src 'self'; frame-ancestors 'none';");
    await next();
});

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseAntiforgery();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
