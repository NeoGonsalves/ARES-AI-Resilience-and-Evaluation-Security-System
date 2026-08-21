using Ares.Web.Models;

namespace Ares.Web.Services;

/// <summary>
/// Service contract for Qdrant vector database operations, embedding search, and RAG retrieval.
/// </summary>
public interface IQdrantCorpusService
{
    /// <summary>
    /// Searches the ares_attack_corpus collection for attack vectors similar to the provided prompt.
    /// </summary>
    Task<IReadOnlyList<QdrantSearchResult<AttackCorpusPayload>>> SearchAttacksAsync(
        string promptText,
        AttackCategory? category = null,
        int limit = 5,
        double minScore = 0.75,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Searches the ares_defense_heuristics collection for mitigation templates matching the attack category.
    /// </summary>
    Task<IReadOnlyList<QdrantSearchResult<DefenseHeuristicPayload>>> SearchDefenseHeuristicsAsync(
        AttackCategory category,
        int limit = 3,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs a full RAG retrieval against both collections to support red-team evaluation and prompt hardening.
    /// </summary>
    Task<RagRetrievalResult> PerformRagRetrievalAsync(
        string targetPrompt,
        AttackCategory category,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Indexes a new redacted attack payload and vector into the ares_attack_corpus.
    /// </summary>
    Task<bool> IndexAttackAsync(
        AttackCorpusPayload payload,
        IReadOnlyList<float>? vector = null,
        CancellationToken cancellationToken = default);
}
