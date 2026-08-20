using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>Contract implemented by the mock today and the FastAPI HTTP client in the next phase.</summary>
public interface IAresApiClient
{
    Task<CreateTestResponse> CreateTestAsync(CreateTestRequest request, CancellationToken cancellationToken);
    Task<TestRun?> GetTestAsync(string testId, CancellationToken cancellationToken);
    Task<TestRun> SimulateTestAsync(string testId, IProgress<ExecutionProgress>? progress, CancellationToken cancellationToken);
    Task<CancelTestResponse> CancelTestAsync(string testId, CancellationToken cancellationToken);
    Task<IReadOnlyList<RecentTestItem>> GetRecentTestsAsync(CancellationToken cancellationToken);
    Task<CorpusSaveResponse> SaveAttackToCorpusAsync(CorpusSaveRequest request, CancellationToken cancellationToken);
    Task<DashboardSummary> GetDashboardSummaryAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<TrendPoint>> GetDashboardTrendsAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<CategoryMetric>> GetCategoryMetricsAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<RuntimeIncident>> GetRecentIncidentsAsync(CancellationToken cancellationToken);
    Task<HardeningComparison> GetHardeningComparisonAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<ProviderHealth>> GetProviderHealthAsync(CancellationToken cancellationToken);
    Task<IReadOnlyList<ModelConfiguration>> GetModelsAsync(AiProvider provider, CancellationToken cancellationToken);
}
