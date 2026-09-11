using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>Contract for the ARES API client — implemented by HttpAresApiClient (live) and MockAresApiClient (dev).</summary>
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
    // Phase 6
    Task<StatsResponse> GetStatsAsync(CancellationToken cancellationToken);
    Task<SearchResponse> SearchAsync(SearchRequest request, CancellationToken cancellationToken);
    Task<HardenResponse> HardenAsync(HardenRequest request, CancellationToken cancellationToken);
}
