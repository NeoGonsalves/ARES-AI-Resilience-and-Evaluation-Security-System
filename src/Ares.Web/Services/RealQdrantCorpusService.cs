using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>
/// Production HTTP client for Qdrant vector corpus operations and RAG retrieval.
/// Queries the live Qdrant Cloud cluster via the FastAPI backend and falls back
/// cleanly to MockQdrantCorpusService if the backend or vector database is offline.
/// </summary>
public sealed class RealQdrantCorpusService : IQdrantCorpusService
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    private readonly HttpClient _http;
    private readonly MockQdrantCorpusService _fallback;

    public RealQdrantCorpusService(HttpClient http, MockQdrantCorpusService fallback)
    {
        _http = http;
        _fallback = fallback;
    }

    public async Task<IReadOnlyList<QdrantSearchResult<AttackCorpusPayload>>> SearchAttacksAsync(
        string promptText,
        AttackCategory? category = null,
        int limit = 5,
        double minScore = 0.75,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var categoryStr = category switch
            {
                AttackCategory.DirectPromptInjection => "instruction_override",
                AttackCategory.RoleManipulation => "role_play_hijack",
                AttackCategory.EncodingOrObfuscation => "encoding_tricks",
                AttackCategory.ToolMisuse => "delimiter_confusion",
                AttackCategory.IndirectPromptInjection => "context_smuggling",
                _ => category?.ToString().ToLowerInvariant()
            };

            var searchReq = new SearchRequest(promptText, categoryStr, limit);
            using var response = await _http.PostAsJsonAsync("api/search", searchReq, JsonOptions, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                // Try alternate endpoint prefix /api/v1/search
                using var alt = await _http.PostAsJsonAsync("api/v1/search", searchReq, JsonOptions, cancellationToken);
                if (!alt.IsSuccessStatusCode)
                    return await _fallback.SearchAttacksAsync(promptText, category, limit, minScore, cancellationToken);
                var altResult = await alt.Content.ReadFromJsonAsync<SearchResponse>(JsonOptions, cancellationToken);
                if (altResult is not null && altResult.Hits.Count > 0)
                    return MapHits(altResult.Hits, category, minScore);
            }
            else
            {
                var result = await response.Content.ReadFromJsonAsync<SearchResponse>(JsonOptions, cancellationToken);
                if (result is not null && result.Hits.Count > 0)
                    return MapHits(result.Hits, category, minScore);
            }
        }
        catch
        {
            // Graceful fallback to mock data on network/timeout error
        }

        return await _fallback.SearchAttacksAsync(promptText, category, limit, minScore, cancellationToken);
    }

    public Task<IReadOnlyList<QdrantSearchResult<DefenseHeuristicPayload>>> SearchDefenseHeuristicsAsync(
        AttackCategory category,
        int limit = 3,
        CancellationToken cancellationToken = default)
    {
        return _fallback.SearchDefenseHeuristicsAsync(category, limit, cancellationToken);
    }

    public async Task<RagRetrievalResult> PerformRagRetrievalAsync(
        string targetPrompt,
        AttackCategory category,
        CancellationToken cancellationToken = default)
    {
        var matchedAttacks = await SearchAttacksAsync(targetPrompt, category, limit: 5, minScore: 0.5, cancellationToken);
        var applicableDefenses = await SearchDefenseHeuristicsAsync(category, limit: 3, cancellationToken);

        var maxRiskScore = matchedAttacks.Count > 0
            ? Math.Round(matchedAttacks.Max(a => a.Score) * 100, 1)
            : 45.0;

        return new RagRetrievalResult(matchedAttacks, applicableDefenses, maxRiskScore, DateTimeOffset.UtcNow);
    }

    public async Task<bool> IndexAttackAsync(
        AttackCorpusPayload payload,
        IReadOnlyList<float>? vector = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var corpusReq = new CorpusSaveRequest(payload.TestId, payload.AnalystNote);
            using var response = await _http.PostAsJsonAsync("api/corpus", corpusReq, JsonOptions, cancellationToken);
            if (response.IsSuccessStatusCode)
            {
                await _fallback.IndexAttackAsync(payload, vector, cancellationToken);
                return true;
            }
        }
        catch
        {
            // fallback
        }

        return await _fallback.IndexAttackAsync(payload, vector, cancellationToken);
    }

    private static IReadOnlyList<QdrantSearchResult<AttackCorpusPayload>> MapHits(
        IReadOnlyList<SearchHit> hits,
        AttackCategory? requestedCategory,
        double minScore)
    {
        var mapped = new List<QdrantSearchResult<AttackCorpusPayload>>();
        foreach (var hit in hits)
        {
            if (hit.Score < minScore) continue;

            var cat = ParseCategory(hit.Category, requestedCategory);
            var sev = hit.Severity.ToLowerInvariant() switch
            {
                "critical" => Severity.Critical,
                "high" => Severity.High,
                "medium" => Severity.Medium,
                "low" => Severity.Low,
                _ => Severity.Safe
            };

            var payload = new AttackCorpusPayload(
                AttackId: hit.Id,
                TestId: $"TST-QDR-{hit.Id[..Math.Min(8, hit.Id.Length)]}",
                Title: $"{hit.Domain} attack vector ({hit.Source})",
                Category: cat,
                Severity: sev,
                Source: AttackSource.Corpus,
                SanitizedPrompt: hit.AttackText,
                PromptSha256: ComputeSha256(hit.AttackText),
                TargetProviders: [AiProvider.Groq, AiProvider.Gemini, AiProvider.NvidiaNim],
                SuccessRate: hit.Score,
                AnalystNote: $"Operator: {hit.OperatorApplied ?? "none"}, Domain: {hit.Domain}",
                IsRedacted: true,
                CreatedAt: DateTimeOffset.UtcNow);

            mapped.Add(new QdrantSearchResult<AttackCorpusPayload>(hit.Id, hit.Score, payload));
        }

        return mapped;
    }

    private static AttackCategory ParseCategory(string categoryStr, AttackCategory? defaultCategory) =>
        categoryStr.ToLowerInvariant() switch
        {
            "role_play_hijack" or "role_manipulation" => AttackCategory.RoleManipulation,
            "instruction_override" or "direct_prompt_injection" => AttackCategory.DirectPromptInjection,
            "delimiter_confusion" or "tool_misuse" => AttackCategory.ToolMisuse,
            "encoding_tricks" or "encoding_or_obfuscation" => AttackCategory.EncodingOrObfuscation,
            "context_smuggling" or "indirect_prompt_injection" => AttackCategory.IndirectPromptInjection,
            _ => defaultCategory ?? AttackCategory.DirectPromptInjection
        };

    private static string ComputeSha256(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
