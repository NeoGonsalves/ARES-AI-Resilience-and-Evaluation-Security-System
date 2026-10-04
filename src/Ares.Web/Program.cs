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
    .AddInteractiveServerComponents();

builder.Services.AddSingleton<IQdrantCorpusService, MockQdrantCorpusService>();
builder.Services.AddScoped<MockAresApiClient>();

var useMock = builder.Configuration.GetValue<bool>("Ares:UseMock", defaultValue: false);
if (useMock)
{
    builder.Services.AddScoped<IAresApiClient>(provider => provider.GetRequiredService<MockAresApiClient>());
}
else
{
    builder.Services.AddHttpClient<FastApiAresApiClient>(client =>
    {
        var baseUrl = builder.Configuration["Ares:ApiBaseUrl"] ?? "http://localhost:8000";
        client.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/");
        client.Timeout = TimeSpan.FromSeconds(120);
        client.DefaultRequestHeaders.Add("X-Ares-User-Email", builder.Configuration["Ares:DevelopmentUserEmail"] ?? "developer@local");
    });
    builder.Services.AddScoped<IAresApiClient>(provider => provider.GetRequiredService<FastApiAresApiClient>());
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
