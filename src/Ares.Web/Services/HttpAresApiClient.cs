using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>
/// Live HTTP client for the ARES FastAPI backend (http://localhost:8000).
/// Replaces MockAresApiClient when Ares:UseMock is false in appsettings.json.
/// </summary>
public sealed class HttpAresApiClient : IAresApiClient
{
    private readonly HttpClient _http;

    private static readonly JsonSerializerOptions _json = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower) },
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    // Stored between CreateTestAsync and SimulateTestAsync calls
    private CreateTestRequest? _pendingRequest;

    public HttpAresApiClient(HttpClient http) => _http = http;

    // -----------------------------------------------------------------------
    // Arena / Tests
    // -----------------------------------------------------------------------

    public async Task<CreateTestResponse> CreateTestAsync(
        CreateTestRequest request, CancellationToken ct)
    {
        _pendingRequest = request;
        // Immediately create (server runs synchronously)
        var resp = await _http.PostAsJsonAsync("/api/tests", request, _json, ct);
        resp.EnsureSuccessStatusCode();
        var run = await resp.Content.ReadFromJsonAsync<TestRunResponse>(_json, ct)
                  ?? throw new InvalidOperationException("Empty response from /api/tests");
        return new CreateTestResponse(run.Id, MapStatus(run.Status), run.CorrelationId, run.CreatedAt);
    }

    public async Task<TestRun?> GetTestAsync(string testId, CancellationToken ct)
    {
        var resp = await _http.GetAsync($"/api/tests/{testId}", ct);
        if (resp.StatusCode == System.Net.HttpStatusCode.NotFound) return null;
        resp.EnsureSuccessStatusCode();
        var run = await resp.Content.ReadFromJsonAsync<TestRunResponse>(_json, ct);
        return run is null ? null : Map(run);
    }

    public async Task<TestRun> SimulateTestAsync(
        string testId, IProgress<ExecutionProgress>? progress, CancellationToken ct)
    {
        progress?.Report(new ExecutionProgress(10, "Initialising", "Connecting to evaluation engine…", 0, 0));
        await Task.Delay(300, ct);

        progress?.Report(new ExecutionProgress(30, "Executing", "Dispatching red-team probes…", 128, 1000));

        // POST to create+run the evaluation
        var request = _pendingRequest ?? throw new InvalidOperationException("Call CreateTestAsync first.");
        var resp = await _http.PostAsJsonAsync("/api/tests", request, _json, ct);
        resp.EnsureSuccessStatusCode();

        progress?.Report(new ExecutionProgress(75, "Analysing", "Classifying responses…", 512, 4000));
        await Task.Delay(200, ct);

        var run = await resp.Content.ReadFromJsonAsync<TestRunResponse>(_json, ct)
                  ?? throw new InvalidOperationException("Empty response from /api/tests");

        progress?.Report(new ExecutionProgress(100, "Complete", "Evaluation finished.", run.TokenEstimate, run.DurationMs));
        return Map(run);
    }

    public async Task<CancelTestResponse> CancelTestAsync(string testId, CancellationToken ct)
    {
        var resp = await _http.PostAsync($"/api/tests/{testId}/cancel", null, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<CancelTestResponse>(_json, ct)
               ?? new CancelTestResponse(testId, TestRunStatus.Cancelled, string.Empty);
    }

    public async Task<IReadOnlyList<RecentTestItem>> GetRecentTestsAsync(CancellationToken ct)
    {
        var items = await _http.GetFromJsonAsync<List<RecentTestItem>>("/api/tests/recent", _json, ct);
        return items ?? [];
    }

    public async Task<CorpusSaveResponse> SaveAttackToCorpusAsync(CorpusSaveRequest request, CancellationToken ct)
    {
        var resp = await _http.PostAsJsonAsync("/api/corpus", request, _json, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<CorpusSaveResponse>(_json, ct)
               ?? throw new InvalidOperationException("Empty response from /api/corpus");
    }

    // -----------------------------------------------------------------------
    // Dashboard
    // -----------------------------------------------------------------------

    public async Task<DashboardSummary> GetDashboardSummaryAsync(CancellationToken ct)
    {
        var r = await _http.GetFromJsonAsync<DashboardSummaryDto>("/api/dashboard/summary", _json, ct)
                ?? throw new InvalidOperationException("Empty /api/dashboard/summary");
        return new DashboardSummary(
            r.Metrics.Select(m => new MetricValue(m.Label, m.Value, m.Change, m.Trend, MapSeverity(m.Status), m.Description)).ToList(),
            r.CorpusSize, r.ProtectedApplications, r.GeneratedAt, r.IsPartial);
    }

    public async Task<IReadOnlyList<TrendPoint>> GetDashboardTrendsAsync(CancellationToken ct)
    {
        var items = await _http.GetFromJsonAsync<List<TrendPointDto>>("/api/dashboard/trends", _json, ct);
        return (items ?? []).Select(t => new TrendPoint(DateOnly.Parse(t.Date), t.Tested, t.Blocked, t.Successful, t.Incidents)).ToList();
    }

    public async Task<IReadOnlyList<CategoryMetric>> GetCategoryMetricsAsync(CancellationToken ct)
    {
        var items = await _http.GetFromJsonAsync<List<CategoryMetricDto>>("/api/dashboard/categories", _json, ct);
        return (items ?? []).Select(c => new CategoryMetric(MapAttackCategory(c.Category), c.Tests, c.Successful, c.Blocked, c.SuccessRate)).ToList();
    }

    public async Task<IReadOnlyList<RuntimeIncident>> GetRecentIncidentsAsync(CancellationToken ct)
    {
        var items = await _http.GetFromJsonAsync<List<RuntimeIncidentDto>>("/api/dashboard/incidents", _json, ct);
        return (items ?? []).Select(i => new RuntimeIncident(i.Id, i.Application, MapAttackCategory(i.Category),
            MapSeverity(i.Severity), i.DetectedAt, i.EnforcementAction, MapIncidentStatus(i.Status), i.CorrelationId)).ToList();
    }

    public async Task<HardeningComparison> GetHardeningComparisonAsync(CancellationToken ct)
    {
        var r = await _http.GetFromJsonAsync<HardeningComparisonDto>("/api/dashboard/hardening", _json, ct)
                ?? throw new InvalidOperationException("Empty /api/dashboard/hardening");
        return new HardeningComparison(r.BaselineSuccessRate, r.HardenedSuccessRate, r.ImprovementPoints,
            r.TestsIncluded, DateOnly.Parse(r.LastCycle));
    }

    public async Task<IReadOnlyList<ProviderHealth>> GetProviderHealthAsync(CancellationToken ct)
    {
        var items = await _http.GetFromJsonAsync<List<ProviderHealthDto>>("/api/dashboard/providers", _json, ct);
        return (items ?? []).Select(p => new ProviderHealth(MapProvider(p.Provider), p.Name,
            MapProviderStatus(p.Status), p.Detail, p.CheckedAt)).ToList();
    }

    public async Task<IReadOnlyList<ModelConfiguration>> GetModelsAsync(AiProvider provider, CancellationToken ct)
    {
        var pStr = provider.ToString().ToLowerInvariant();
        var items = await _http.GetFromJsonAsync<List<ModelConfigDto>>($"/api/models?provider={pStr}", _json, ct);
        return (items ?? []).Select(m => new ModelConfiguration(MapProvider(m.Provider) ?? provider,
            m.Id, m.DisplayName, m.ContextWindow, m.IsAvailable)).ToList();
    }

    // -----------------------------------------------------------------------
    // Phase 6: Stats / Search / Harden
    // -----------------------------------------------------------------------

    public async Task<StatsResponse> GetStatsAsync(CancellationToken ct)
    {
        var result = await _http.GetFromJsonAsync<StatsResponse>("/api/stats", _json, ct);
        return result ?? throw new InvalidOperationException("Empty /api/stats response");
    }


    public async Task<SearchResponse> SearchAsync(SearchRequest request, CancellationToken ct)
    {
        var resp = await _http.PostAsJsonAsync("/api/search", request, _json, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<SearchResponse>(_json, ct)
               ?? new SearchResponse(request.Query, 0, []);
    }

    public async Task<HardenResponse> HardenAsync(HardenRequest request, CancellationToken ct)
    {
        var resp = await _http.PostAsJsonAsync("/api/harden", request, _json, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<HardenResponse>(_json, ct)
               ?? throw new InvalidOperationException("Empty /api/harden response");
    }

    // -----------------------------------------------------------------------
    // Mapping helpers (snake_case API → C# enum)
    // -----------------------------------------------------------------------

    private static TestRunStatus MapStatus(string? s) => s?.ToLowerInvariant() switch
    {
        "completed" => TestRunStatus.Completed, "failed" => TestRunStatus.Failed,
        "cancelled" => TestRunStatus.Cancelled, "running"  => TestRunStatus.Running,
        "queued"    => TestRunStatus.Queued,    "blocked"  => TestRunStatus.Blocked,
        _           => TestRunStatus.Idle,
    };

    private static Severity MapSeverity(string? s) => s?.ToLowerInvariant() switch
    {
        "low" => Severity.Low, "medium" => Severity.Medium,
        "high" => Severity.High, "critical" => Severity.Critical,
        _ => Severity.Safe,
    };

    private static AttackCategory MapAttackCategory(string? s) => s?.ToLowerInvariant() switch
    {
        "role_manipulation" or "role_play_hijack"    => AttackCategory.RoleManipulation,
        "encoding_or_obfuscation" or "encoding_tricks" => AttackCategory.EncodingOrObfuscation,
        "indirect_prompt_injection" or "context_smuggling" => AttackCategory.IndirectPromptInjection,
        "delimiter_confusion" or "tool_misuse"       => AttackCategory.ToolMisuse,
        _                                            => AttackCategory.DirectPromptInjection,
    };

    private static IncidentStatus MapIncidentStatus(string? s) => s?.ToLowerInvariant() switch
    {
        "investigating" => IncidentStatus.Investigating, "resolved" => IncidentStatus.Resolved,
        "suppressed"    => IncidentStatus.Suppressed,    _ => IncidentStatus.Open,
    };

    private static AiProvider? MapProvider(string? s) => s?.ToLowerInvariant() switch
    {
        "groq" => AiProvider.Groq, "gemini" => AiProvider.Gemini,
        "nvidia_nim" => AiProvider.NvidiaNim, "openai" => AiProvider.OpenAI, _ => null,
    };

    private static ProviderStatus MapProviderStatus(string? s) => s?.ToLowerInvariant() switch
    {
        "degraded" => ProviderStatus.Degraded, "unavailable" => ProviderStatus.Unavailable,
        "not_configured" => ProviderStatus.NotConfigured, _ => ProviderStatus.Operational,
    };

    private static TestRun Map(TestRunResponse r) => new(
        r.Id, MapConfig(r.Configuration), MapStatus(r.Status), r.CreatedAt, r.CompletedAt,
        r.DurationMs, r.TokenEstimate, MapAnalysis(r.Analysis), r.Log, r.CorrelationId, r.FailureReason);

    private static ArenaTestConfiguration MapConfig(ArenaTestConfigDto c) => new()
    {
        TestName = c.TestName, TargetApplication = c.TargetApplication,
        SystemPrompt = c.SystemPrompt, UserPrompt = c.UserPrompt,
        Model = c.Model, Temperature = c.Temperature,
        MaxResponseTokens = c.MaxResponseTokens, VariationCount = c.VariationCount,
        IncludeHardenedComparison = c.IncludeHardenedComparison,
    };

    private static SecurityClassification? MapAnalysis(SecurityClassificationDto? a)
    {
        if (a is null) return null;
        return new SecurityClassification(a.RiskScore, MapSeverity(a.Severity), a.AttackSucceeded,
            a.RuntimeClassification,
            a.Detections.Select(d => new DetectionResult(d.RuleId, d.Name, MapSeverity(d.Severity), d.Explanation, d.Triggered)).ToList(),
            a.Evidence.Select(e => new EvidenceItem(e.Id, e.Source, e.Summary, e.Similarity, MapAttackCategory(e.Category), e.RetrievedAt)).ToList(),
            a.Hardening is null ? null : new PromptHardeningResult(a.Hardening.Summary, a.Hardening.RecommendedChange, a.Hardening.HardenedPrompt, a.Hardening.ImprovementPoints, a.Hardening.GeneratedAt),
            a.Comparison is null ? null : new ResponseComparison(a.Comparison.BaselineResponse, a.Comparison.HardenedResponse, a.Comparison.DifferenceSummary));
    }

    // -----------------------------------------------------------------------
    // DTO types (snake_case JSON → these internal DTOs → public models)
    // -----------------------------------------------------------------------
    private sealed record TestRunResponse(string Id, ArenaTestConfigDto Configuration, string Status,
        DateTimeOffset CreatedAt, DateTimeOffset? CompletedAt, int DurationMs, int TokenEstimate,
        SecurityClassificationDto? Analysis, List<ExecutionLogEvent> Log, string CorrelationId, string? FailureReason);
    private sealed record ArenaTestConfigDto(string TestName, string TargetApplication, string SystemPrompt,
        string UserPrompt, string Provider, string Model, string AttackSource, List<string> AttackCategories,
        double Temperature, int MaxResponseTokens, int VariationCount, bool IncludeHardenedComparison);
    private sealed record SecurityClassificationDto(int RiskScore, string Severity, bool AttackSucceeded,
        string RuntimeClassification, List<DetectionDto> Detections, List<EvidenceDto> Evidence,
        HardeningDto? Hardening, ComparisonDto? Comparison);
    private sealed record DetectionDto(string RuleId, string Name, string Severity, string Explanation, bool Triggered);
    private sealed record EvidenceDto(string Id, string Source, string Summary, double Similarity, string Category, DateTimeOffset RetrievedAt);
    private sealed record HardeningDto(string Summary, string RecommendedChange, string HardenedPrompt, int ImprovementPoints, DateTimeOffset GeneratedAt);
    private sealed record ComparisonDto(string BaselineResponse, string HardenedResponse, string DifferenceSummary);
    private sealed record DashboardSummaryDto(List<MetricValueDto> Metrics, int CorpusSize, int ProtectedApplications, DateTimeOffset GeneratedAt, bool IsPartial);
    private sealed record MetricValueDto(string Label, string Value, string Change, string Trend, string Status, string Description);
    private sealed record TrendPointDto(string Date, int Tested, int Blocked, int Successful, int Incidents);
    private sealed record CategoryMetricDto(string Category, int Tests, int Successful, int Blocked, int SuccessRate);
    private sealed record RuntimeIncidentDto(string Id, string Application, string Category, string Severity, DateTimeOffset DetectedAt, string EnforcementAction, string Status, string CorrelationId);
    private sealed record ProviderHealthDto(string? Provider, string Name, string Status, string Detail, DateTimeOffset CheckedAt);
    private sealed record HardeningComparisonDto(int BaselineSuccessRate, int HardenedSuccessRate, int ImprovementPoints, int TestsIncluded, string LastCycle);
    private sealed record ModelConfigDto(string Provider, string Id, string DisplayName, int ContextWindow, bool IsAvailable);
}
