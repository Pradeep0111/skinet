using API.DTOs.Assistant;

namespace API.DTOs;

public class AssistantProductDto
{
    public int Id { get; set; }
    public required string Name { get; set; }
    public required string Description { get; set; }
    public decimal Price { get; set; }
    public decimal EffectivePrice { get; set; }
    public required string PictureUrl { get; set; }
    public required string Brand { get; set; }
    public required string Type { get; set; }
    public string? Category { get; set; }
    public string? Subcategory { get; set; }
    public int QuantityInStock { get; set; }
    public string? Sku { get; set; }
    public decimal? UnitSize { get; set; }
    public string? UnitLabel { get; set; }
    public List<string> Tags { get; set; } = [];
    public List<string> DietaryLabels { get; set; } = [];
    public List<string> Allergens { get; set; } = [];
    public string? Ingredients { get; set; }
    public NutritionFactsDto? Nutrition { get; set; }
    public string? Origin { get; set; }
    public decimal? AverageRating { get; set; }
    public int? ReviewCount { get; set; }
    public PromotionDto? Promotion { get; set; }
    public string? SubstitutionGroup { get; set; }
}