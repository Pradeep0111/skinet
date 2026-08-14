using API.DTOs.Assistant;
using System.Security.Claims;

namespace API.Services.Assistant;

public interface IAssistantContextService
{
    Task<List<CartItemContext>> BuildCartContextAsync(string? cartId);
    Task<List<ProductPreferenceContext>> BuildPurchaseHistoryAsync(ClaimsPrincipal user);
    bool ValidateServiceKey(string? serviceKey);
    ChatResponseDto CreateUnavailableResponse(string conversationId);
}
