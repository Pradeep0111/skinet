namespace API.DTOs.Assistant;

public class ChatResponseDto
{
    public string ConversationId { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public List<AssistantProductDto> Products { get; set; } = [];
    public List<ProductComparisonDto> Comparisons { get; set; } = [];
    public List<ProposedActionDto> ProposedActions { get; set; } = [];
    public List<string> SuggestedPrompts { get; set; } = [];
}