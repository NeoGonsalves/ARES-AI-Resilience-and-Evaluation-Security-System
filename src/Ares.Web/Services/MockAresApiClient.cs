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

    // ── Arena Platform ────────────────────────────────────────────────────────

    private static readonly IReadOnlyList<Challenge> _challenges = MockData.Challenges();
    private static readonly IReadOnlyList<ChallengeRoom> _rooms = MockData.Rooms();
    private static readonly IReadOnlyList<LearningPath> _paths = MockData.LearningPaths();
    private static readonly IReadOnlyList<OrgAssessment> _assessments = [.. MockData.OrgAssessments()];
    private readonly List<OrgAssessment> _assessmentsMutable = [.. MockData.OrgAssessments()];
    private readonly List<Challenge> _challengesMutable = [.. MockData.Challenges()];
    private readonly List<ChallengeSubmission> _submissions = [];
    private IReadOnlyList<ChallengeProgressItem> _progress = MockData.MockProgress();
    private UserProfile _profile = MockData.MockProfile();

    public Task<ChallengePageResult> GetChallengesAsync(ChallengeTrack? track, DifficultyTier? tier, AttackCategory? category, string? search, int page, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        const int pageSize = 10;
        var query = _challengesMutable.AsEnumerable();
        if (track.HasValue) query = query.Where(c => c.Track == track.Value);
        if (tier.HasValue) query = query.Where(c => c.Tier == tier.Value);
        if (category.HasValue) query = query.Where(c => c.Category == category.Value);
        if (!string.IsNullOrWhiteSpace(search)) query = query.Where(c => c.Title.Contains(search, StringComparison.OrdinalIgnoreCase) || c.Tags.Any(t => t.Contains(search, StringComparison.OrdinalIgnoreCase)));
        var filtered = query.ToList();
        var items = filtered.Skip((page - 1) * pageSize).Take(pageSize).ToList();
        return Task.FromResult(new ChallengePageResult(items, _progress, filtered.Count, page, pageSize));
    }

    public Task<Challenge?> GetChallengeAsync(string challengeId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_challengesMutable.FirstOrDefault(c => c.Id == challengeId));
    }

    public Task<IReadOnlyList<ChallengeRoom>> GetRoomsAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_rooms);
    }

    public Task<ChallengeRoom?> GetRoomAsync(string roomId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_rooms.FirstOrDefault(r => r.Id == roomId));
    }

    public Task<IReadOnlyList<LearningPath>> GetLearningPathsAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_paths);
    }

    public Task<SubmitChallengeResponse> SubmitChallengeAsync(SubmitChallengeRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var run = RequireRun(request.TestRunId);
        var challenge = _challengesMutable.FirstOrDefault(c => c.Id == request.ChallengeId)
            ?? throw new KeyNotFoundException($"Challenge {request.ChallengeId} was not found.");
        var score = MockData.ComputeScore(run, challenge.Track);
        var subId = $"SUB-{request.ChallengeId}-{_submissions.Count + 1:D3}";
        var isFirstSubmission = !_submissions.Any(s => s.ChallengeId == request.ChallengeId);
        var isBest = !_submissions.Any(s => s.ChallengeId == request.ChallengeId && s.Score.Total >= score.Total);
        var submission = new ChallengeSubmission(subId, request.ChallengeId, _profile.Id, request.TestRunId, score, DateTimeOffset.UtcNow, isBest);
        lock (_gate) _submissions.Add(submission);

        // Update progress
        var progList = _progress.ToList();
        var existing = progList.FindIndex(p => p.ChallengeId == request.ChallengeId);
        var newStatus = score.Total > 0 ? ChallengeStatus.Completed : ChallengeStatus.Available;
        var newItem = new ChallengeProgressItem(request.ChallengeId, challenge.Title, challenge.Track, challenge.Tier, newStatus, isBest ? score.Total : progList.ElementAtOrDefault(existing)?.BestScore, DateTimeOffset.UtcNow);
        if (existing >= 0) progList[existing] = newItem; else progList.Add(newItem);
        _progress = progList;

        // Award XP and badge
        var xpGained = score.Total;
        var newTotal = _profile.XpTotal + xpGained;
        var newLevel = newTotal / 500 + 1;
        var newThisLevel = newTotal % 500;
        UserBadge? badge = null;
        var badges = _profile.Badges.ToList();
        if (isFirstSubmission && !badges.Any(b => b.Type == BadgeType.FirstBlood))
        {
            badge = new(BadgeType.FirstBlood, "First Blood", "Complete your first challenge.", DateTimeOffset.UtcNow, request.ChallengeId);
            badges.Add(badge);
        }
        _profile = _profile with
        {
            XpTotal = newTotal,
            Level = newLevel,
            XpThisLevel = newThisLevel,
            Badges = badges,
            ChallengesSolved = _profile.ChallengesSolved + (isFirstSubmission ? 1 : 0),
            AttackerSolved = _profile.AttackerSolved + (isFirstSubmission && challenge.Track == ChallengeTrack.Attacker ? 1 : 0),
            DefenderSolved = _profile.DefenderSolved + (isFirstSubmission && challenge.Track == ChallengeTrack.Defender ? 1 : 0)
        };

        var nextId = _challengesMutable.FirstOrDefault(c => c.Id != request.ChallengeId && c.Track == challenge.Track && c.Tier == challenge.Tier && !_progress.Any(p => p.ChallengeId == c.Id && p.Status == ChallengeStatus.Completed))?.Id;
        return Task.FromResult(new SubmitChallengeResponse(submission, badge is not null, badge, nextId));
    }

    public Task<IReadOnlyList<ChallengeSubmission>> GetMySubmissionsAsync(string challengeId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult<IReadOnlyList<ChallengeSubmission>>(_submissions.Where(s => s.ChallengeId == challengeId).OrderByDescending(s => s.SubmittedAt).ToList());
    }

    public Task<IReadOnlyList<ChallengeProgressItem>> GetMyProgressAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_progress);
    }

    public Task<UserProfile> GetMyProfileAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(_profile);
    }

    public Task<IReadOnlyList<OrgAssessment>> GetOrgAssessmentsAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult<IReadOnlyList<OrgAssessment>>(_assessmentsMutable);
    }

    public Task<OrgAssessment> CreateOrgAssessmentAsync(CreateOrgAssessmentRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var created = request.Draft with { Id = $"ASS-{_assessmentsMutable.Count + 1:D3}" };
        lock (_gate) _assessmentsMutable.Add(created);
        return Task.FromResult(created);
    }

    public Task<Challenge> CreateChallengeAsync(CreateChallengeRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var created = request.Draft with { Id = $"CHK-CUSTOM-{_challengesMutable.Count + 1:D3}" };
        lock (_gate) _challengesMutable.Add(created);
        return Task.FromResult(created);
    }

    public Task<Challenge> UpdateChallengeAsync(UpdateChallengeRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var idx = _challengesMutable.FindIndex(c => c.Id == request.Updated.Id);
        if (idx < 0) throw new KeyNotFoundException($"Challenge {request.Updated.Id} was not found.");
        lock (_gate) _challengesMutable[idx] = request.Updated;
        return Task.FromResult(request.Updated);
    }
}
