using API.DTOs.Assistant;

namespace API.Services.Assistant;

public interface IAssistantClient
{
    Task<ChatResponseDto?> SendChatAsync(AssistantChatRequest request, CancellationToken cancellationToken);
    Task<bool> IsAvailableAsync(CancellationToken cancellationToken);
}