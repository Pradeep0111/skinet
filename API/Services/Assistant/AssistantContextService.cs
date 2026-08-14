using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using API.DTOs.Assistant;
using API.Extensions;
using Core.Entities.OrderAggregate;
using Core.Interfaces;
using Core.Specifications;

namespace API.Services.Assistant;

public class AssistantContextService(
    ICartService cartService,
    IUnitOfWork unit,
    IConfiguration configuration) : IAssistantContextService
{
    public async Task<List<CartItemContext>> BuildCartContextAsync(string? cartId)
    {
        if (string.IsNullOrWhiteSpace(cartId)) return [];

        var cart = await cartService.GetCartAsync(cartId);

        // Python accepts at most 100 cart-context items.
        return cart?.Items
            .Take(100)
            .Select(item => new CartItemContext
            {
                ProductId = item.ProductId,
                Quantity = item.Quantity
            })
            .ToList() ?? [];
    }

    public async Task<List<ProductPreferenceContext>> BuildPurchaseHistoryAsync(
        ClaimsPrincipal user)
    {
        if (user.Identity?.IsAuthenticated != true) return [];

        var orders = await unit.Repository<Order>()
            .ListAsync(new OrderSpecification(user.GetEmail()));

        return orders
            .SelectMany(order => order.OrderItems.Select(item => new
            {
                order.Id,
                order.OrderDate,
                ProductId = item.ItemOrdered.ProductId
            }))
            .GroupBy(item => item.ProductId)
            .Select(group => new ProductPreferenceContext
            {
                ProductId = group.Key,
                PurchaseCount = group
                    .Select(item => item.Id)
                    .Distinct()
                    .Count(),
                LastPurchasedAt = new DateTimeOffset(
                    DateTime.SpecifyKind(
                        group.Max(item => item.OrderDate),
                        DateTimeKind.Utc))
            })
            .OrderByDescending(item => item.LastPurchasedAt)
            .Take(50)
            .ToList();
    }

    public bool ValidateServiceKey(string? serviceKey)
    {
        var expectedServiceKey = configuration["Assistant:ServiceKey"];

        if (string.IsNullOrEmpty(expectedServiceKey)
            || string.IsNullOrEmpty(serviceKey))
        {
            return false;
        }

        var expectedHash = SHA256.HashData(
            Encoding.UTF8.GetBytes(expectedServiceKey));

        var providedHash = SHA256.HashData(
            Encoding.UTF8.GetBytes(serviceKey));

        return CryptographicOperations.FixedTimeEquals(
            expectedHash,
            providedHash);
    }

    public ChatResponseDto CreateUnavailableResponse(string conversationId)
    {
        return new ChatResponseDto
        {
            ConversationId = conversationId,
            Message = "The shopping assistant is currently unavailable."
        };
    }
}