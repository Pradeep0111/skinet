using API.DTOs;
using API.DTOs.Assistant;
using API.Extensions;
using API.RequestHelper;
using API.Services.Assistant;
using Core.Entities;
using Core.Interfaces;
using Core.Specifications;
using Microsoft.AspNetCore.Mvc;

namespace API.Controllers.Assistant;

public class AssistantController(
    IConfiguration configuration,
    IUnitOfWork unit,
    IAssistantClient assistantClient,
    IAssistantContextService contextService) : BaseAPIController
{
    [HttpGet("status")]
    public async Task<IActionResult> GetStatus()
    {
        var enabled = configuration.GetValue<bool>("Assistant:Enabled");

        var available = enabled && await assistantClient.IsAvailableAsync(HttpContext.RequestAborted);

        return Ok(new AssistantStatusDto
        {
            Enabled = enabled,
            Available = available
        });
    }

    [HttpPost("chat")]
    public async Task<ActionResult<ChatResponseDto>> Chat(ChatRequestDto request)
    {
        var conversationId = request.ConversationId ?? Guid.NewGuid().ToString("N");
        var maxMessageLength = configuration.GetValue<int?>("Assistant:MaxMessageLength") ?? 2000;

        if (request.Message.Length > maxMessageLength)
            return BadRequest($"Message cannot exceed {maxMessageLength} characters.");

        if (!configuration.GetValue<bool>("Assistant:Enabled"))
            return Ok(contextService.CreateUnavailableResponse(conversationId));

        var assistantRequest = new AssistantChatRequest
        {
            Message = request.Message,
            ConversationId = conversationId,
            CartItems = await contextService.BuildCartContextAsync(request.CartId),
            PurchaseHistory = await contextService.BuildPurchaseHistoryAsync(User)
        };

        var response = await assistantClient.SendChatAsync(assistantRequest, HttpContext.RequestAborted);
        return Ok(response ?? contextService.CreateUnavailableResponse(conversationId));
    }

    [HttpGet("catalog")]
    public async Task<ActionResult<Pagination<AssistantProductDto>>> GetCatalog(
        [FromQuery] ProductSpecParams specParams,
        [FromHeader(Name = "X-Assistant-Service-Key")] string? serviceKey)
    {
        if (!contextService.ValidateServiceKey(serviceKey)) return Unauthorized();

        var specification = new ProductSpecification(specParams);
        var products = await unit.Repository<Product>().ListAsync(specification);
        var count = await unit.Repository<Product>().CountAsync(specification);

        return Ok(new Pagination<AssistantProductDto>(
            specParams.PageIndex,
            specParams.PageSize,
            count,
            products.Select(product => product.ToAssistantProductDto()).ToList()));
    }
}