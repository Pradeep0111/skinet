using System.ComponentModel.DataAnnotations;

namespace API.DTOs.Assistant;

public class ChatRequestDto
{
    [Required]
    [StringLength(2000)]
    public string Message { get; set; } = string.Empty;
    public string? ConversationId { get; set; }
    public string? CartId { get; set; }
}