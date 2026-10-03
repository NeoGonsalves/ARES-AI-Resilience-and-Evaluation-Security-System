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

    // ── Arena Platform ────────────────────────────────────────────────────────

    // Challenge catalogue
    Task<ChallengePageResult> GetChallengesAsync(ChallengeTrack? track, DifficultyTier? tier, AttackCategory? category, string? search, int page, CancellationToken cancellationToken);
    Task<Challenge?> GetChallengeAsync(string challengeId, CancellationToken cancellationToken);
    Task<IReadOnlyList<ChallengeRoom>> GetRoomsAsync(CancellationToken cancellationToken);
    Task<ChallengeRoom?> GetRoomAsync(string roomId, CancellationToken cancellationToken);
    Task<IReadOnlyList<LearningPath>> GetLearningPathsAsync(CancellationToken cancellationToken);

    // Submission & scoring
    Task<SubmitChallengeResponse> SubmitChallengeAsync(SubmitChallengeRequest request, CancellationToken cancellationToken);
    Task<IReadOnlyList<ChallengeSubmission>> GetMySubmissionsAsync(string challengeId, CancellationToken cancellationToken);
    Task<IReadOnlyList<ChallengeProgressItem>> GetMyProgressAsync(CancellationToken cancellationToken);

    // Profile
    Task<UserProfile> GetMyProfileAsync(CancellationToken cancellationToken);

    // Org / Admin
    Task<IReadOnlyList<OrgAssessment>> GetOrgAssessmentsAsync(CancellationToken cancellationToken);
    Task<OrgAssessment> CreateOrgAssessmentAsync(CreateOrgAssessmentRequest request, CancellationToken cancellationToken);
    Task<Challenge> CreateChallengeAsync(CreateChallengeRequest request, CancellationToken cancellationToken);
    Task<Challenge> UpdateChallengeAsync(UpdateChallengeRequest request, CancellationToken cancellationToken);
}
