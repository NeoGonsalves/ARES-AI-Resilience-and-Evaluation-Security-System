using Ares.Web.Models;
using Ares.Web.Services;
using Xunit;

namespace Ares.Web.Tests;

public sealed class MockDataTests
{
    [Fact]
    public void Recent_tests_cover_required_terminal_states()
    {
        var statuses = MockData.RecentTestRuns().Select(run => run.Status).ToHashSet();

        Assert.Contains(TestRunStatus.Completed, statuses);
        Assert.Contains(TestRunStatus.Blocked, statuses);
        Assert.Contains(TestRunStatus.Failed, statuses);
        Assert.Contains(TestRunStatus.Cancelled, statuses);
    }

    [Fact]
    public void Direct_injection_produces_critical_success_with_comparison()
    {
        var configuration = new ArenaTestConfiguration { AttackCategories = [AttackCategory.DirectPromptInjection] };

        var result = MockData.CreateAnalysis(configuration);

        Assert.NotNull(result.Analysis);
        Assert.Equal(Severity.Critical, result.Analysis!.Severity);
        Assert.True(result.Analysis.AttackSucceeded);
        Assert.NotNull(result.Analysis.Comparison);
    }

    [Fact]
    public void NIM_tool_misuse_is_a_safe_provider_failure()
    {
        var configuration = new ArenaTestConfiguration { Provider = AiProvider.NvidiaNim, Model = "meta/llama-3.1-70b-instruct", AttackCategories = [AttackCategory.ToolMisuse] };

        var result = MockData.CreateAnalysis(configuration);

        Assert.Null(result.Analysis);
        Assert.NotNull(result.FailureReason);
        Assert.DoesNotContain("key", result.FailureReason!, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Display_labels_are_human_readable()
    {
        Assert.Equal("Direct prompt injection", AttackCategory.DirectPromptInjection.ToLabel());
        Assert.Equal("NVIDIA NIM", AiProvider.NvidiaNim.ToLabel());
    }

    [Theory]
    [InlineData(AttackCategory.DirectPromptInjection, AiProvider.OpenAI, "gpt-4.1-mini", TestRunStatus.Completed)]
    [InlineData(AttackCategory.DataExfiltration, AiProvider.Gemini, "gemini-2.5-flash", TestRunStatus.Blocked)]
    [InlineData(AttackCategory.ToolMisuse, AiProvider.NvidiaNim, "meta/llama-3.1-70b-instruct", TestRunStatus.Failed)]
    public async Task Simulated_run_reaches_expected_terminal_state(AttackCategory category, AiProvider provider, string model, TestRunStatus expected)
    {
        var client = new MockAresApiClient();
        var configuration = new ArenaTestConfiguration { Provider = provider, Model = model, AttackCategories = [category] };
        var created = await client.CreateTestAsync(new CreateTestRequest(configuration), CancellationToken.None);
        var result = await client.SimulateTestAsync(created.TestId, null, CancellationToken.None);

        Assert.Equal(expected, result.Status);
        Assert.Contains(result.Log, item => item.Stage is "Completed" or "Provider failure");
    }

    [Fact]
    public async Task Cancelled_run_is_persisted_as_cancelled()
    {
        var client = new MockAresApiClient();
        var created = await client.CreateTestAsync(new CreateTestRequest(new ArenaTestConfiguration()), CancellationToken.None);

        var cancellation = await client.CancelTestAsync(created.TestId, CancellationToken.None);
        var result = await client.GetTestAsync(created.TestId, CancellationToken.None);

        Assert.Equal(TestRunStatus.Cancelled, cancellation.Status);
        Assert.Equal(TestRunStatus.Cancelled, result!.Status);
    }
}
