using System.Net.Http.Json;
using API.DTOs.Assistant;

namespace API.Services.Assistant;

public class AssistantClient(HttpClient httpClient, IConfiguration configuration, ILogger<AssistantClient> logger) : IAssistantClient
{
    private static readonly HashSet<string> AllowedActionTypes = ["add_to_cart"];

    public async Task<ChatResponseDto?> SendChatAsync(AssistantChatRequest request, CancellationToken cancellationToken)
    {
        try
        {
            using var message = new HttpRequestMessage(HttpMethod.Post, "api/chat")
            {
                Content = JsonContent.Create(request)
            };

            AddServiceKey(message);

            using var response = await httpClient.SendAsync(message, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                logger.LogWarning("Assistant service returned status code {StatusCode}", response.StatusCode);
                return null;
            }

            var result = await response.Content.ReadFromJsonAsync<ChatResponseDto>(cancellationToken);
            return result is not null && IsValidResponse(result) ? result : null;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            logger.LogWarning("Assistant service request timed out or was cancelled");
            return null;
        }
        catch (HttpRequestException exception)
        {
            logger.LogWarning(exception, "Assistant service could not be reached");
            return null;
        }
    }

    public async Task<bool> IsAvailableAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "health");
            AddServiceKey(request);

            using var response = await httpClient.SendAsync(request, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            return false;
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }

    private void AddServiceKey(HttpRequestMessage request)
    {
        var serviceKey = configuration["Assistant:ServiceKey"];
        if (!string.IsNullOrEmpty(serviceKey))
            request.Headers.Add("X-Assistant-Service-Key", serviceKey);
    }

    private static bool IsValidResponse(ChatResponseDto response)
    {
        if (string.IsNullOrWhiteSpace(response.ConversationId) || string.IsNullOrWhiteSpace(response.Message))
            return false;

        return response.ProposedActions.All(action =>
            AllowedActionTypes.Contains(action.Type)
            && action.ProductId > 0
            && action.Quantity is > 0 and <= 100);
    }
}