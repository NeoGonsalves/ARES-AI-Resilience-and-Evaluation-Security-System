using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>Deterministic local data only. Never sends prompt content or credentials over the network.</summary>
public sealed class MockAresApiClient : IAresApiClient
{
    private readonly object _gate = new();
    private readonly Dictionary<string, TestRun> _runs = MockData.RecentTestRuns().ToDictionary(run => run.Id);

    public Task<CreateTestResponse> CreateTestAsync(CreateTestRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var id = $"TST-{DateTime.UtcNow:yyMMdd}-{_runs.Count + 101:D3}";
        var correlationId = $"ares-{Guid.NewGuid():N}"[..17];
        var run = new TestRun(id, request.Configuration, TestRunStatus.Queued, DateTimeOffset.UtcNow, null, 0, 0, null,
            [new ExecutionLogEvent(DateTimeOffset.UtcNow, "Queued", "Test configuration accepted. Prompt content is redacted in audit logs.")], correlationId);
        lock (_gate) _runs[id] = run;
        return Task.FromResult(new CreateTestResponse(id, run.Status, correlationId, run.CreatedAt));
    }

    public Task<TestRun?> GetTestAsync(string testId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        lock (_gate) return Task.FromResult(_runs.GetValueOrDefault(testId));
    }

    public async Task<TestRun> SimulateTestAsync(string testId, IProgress<ExecutionProgress>? progress, CancellationToken cancellationToken)
    {
        var run = await RequireRunAsync(testId, cancellationToken);
        run = Update(run with { Status = TestRunStatus.Running }, "Validation", "Configuration validated; preparing isolated test request.");
        var stages = new[]
        {
            new ExecutionProgress(12, "Attack selection", "Selected controlled attack variation from the configured source.", 118, 210),
            new ExecutionProgress(31, "Evidence retrieval", "Retrieved relevant sanitized failure evidence from the corpus index.", 244, 490),
            new ExecutionProgress(55, "Provider evaluation", $"Testing {run.Configuration.Provider} / {run.Configuration.Model} through its adapter.", 508, 940),
            new ExecutionProgress(74, "Runtime classification", "Evaluating model output against enforcement and detection rules.", 621, 1240),
            new ExecutionProgress(90, "Prompt hardening", "Producing a controlled hardening comparison.", 738, 1580)
        };

        foreach (var stage in stages)
        {
            await Task.Delay(420, cancellationToken);
            progress?.Report(stage);
            run = Update(run, stage.Stage, stage.Message);
        }

        var result = MockData.CreateAnalysis(run.Configuration);
        var finalStatus = result.FailureReason is not null ? TestRunStatus.Failed : result.Analysis!.RuntimeClassification == "Blocked by enforcement" ? TestRunStatus.Blocked : TestRunStatus.Completed;
        var completed = Update(run with
        {
            Status = finalStatus,
            CompletedAt = DateTimeOffset.UtcNow,
            DurationMilliseconds = 1830,
            TokenEstimate = 786,
            Analysis = result.Analysis,
            FailureReason = result.FailureReason
        }, finalStatus == TestRunStatus.Failed ? "Provider failure" : "Completed", result.FailureReason ?? "Controlled test complete. Result available for analysis.");
        progress?.Report(new ExecutionProgress(100, finalStatus == TestRunStatus.Failed ? "Failed" : "Completed", completed.FailureReason ?? "Test complete.", completed.TokenEstimate, completed.DurationMilliseconds));
        return completed;
    }

    public Task<CancelTestResponse> CancelTestAsync(string testId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var run = RequireRun(testId);
        var cancelled = Update(run with { Status = TestRunStatus.Cancelled, CompletedAt = DateTimeOffset.UtcNow }, "Cancelled", "Test cancelled by analyst before completion.", "warning");
        return Task.FromResult(new CancelTestResponse(testId, cancelled.Status, cancelled.CorrelationId));
    }

    public Task<IReadOnlyList<RecentTestItem>> GetRecentTestsAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        lock (_gate)
        {
            return Task.FromResult<IReadOnlyList<RecentTestItem>>(_runs.Values.OrderByDescending(run => run.CreatedAt).Take(12)
                .Select(run => new RecentTestItem(run.Id, run.CreatedAt, run.Configuration.AttackCategories.FirstOrDefault(), run.Configuration.Provider, run.Configuration.Model, run.Analysis?.RiskScore ?? 0, run.Status)).ToList());
        }
    }

    public Task<CorpusSaveResponse> SaveAttackToCorpusAsync(CorpusSaveRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var run = RequireRun(request.TestId);
        if (run.Analysis is null) throw new InvalidOperationException("A completed result is required before it can be saved to the corpus.");
        return Task.FromResult(new CorpusSaveResponse($"ATK-{run.Id[4..]}", request.TestId, DateTimeOffset.UtcNow, run.CorrelationId));
    }

    public Task<DashboardSummary> GetDashboardSummaryAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.DashboardSummary());
    public Task<IReadOnlyList<TrendPoint>> GetDashboardTrendsAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.Trends());
    public Task<IReadOnlyList<CategoryMetric>> GetCategoryMetricsAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.CategoryMetrics());
    public Task<IReadOnlyList<RuntimeIncident>> GetRecentIncidentsAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.Incidents());
    public Task<HardeningComparison> GetHardeningComparisonAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.Hardening());
    public Task<IReadOnlyList<ProviderHealth>> GetProviderHealthAsync(CancellationToken cancellationToken) => Task.FromResult(MockData.Health());
    public Task<IReadOnlyList<ModelConfiguration>> GetModelsAsync(AiProvider provider, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<ModelConfiguration> models = MockData.Models().Where(model => model.Provider == provider).ToList();
        return Task.FromResult(models);
    }

    private async Task<TestRun> RequireRunAsync(string testId, CancellationToken cancellationToken) => await GetTestAsync(testId, cancellationToken) ?? throw new KeyNotFoundException($"Test {testId} was not found.");
    private TestRun RequireRun(string testId) { lock (_gate) return _runs.GetValueOrDefault(testId) ?? throw new KeyNotFoundException($"Test {testId} was not found."); }
    private TestRun Update(TestRun run, string stage, string message, string level = "info") => Update(run with { Log = [.. run.Log, new ExecutionLogEvent(DateTimeOffset.UtcNow, stage, message, level)] });
    private TestRun Update(TestRun run) { lock (_gate) { _runs[run.Id] = run; return run; } }
}
