using System;

namespace Core.Entities;

public class Product : BaseEntity
{
    public required string Name { get; set; }
    public required string Description { get; set; }
    public decimal Price { get; set; }
    public required string PictureUrl { get; set; }
    public required string Type { get; set; }
    public required string Brand { get; set; }
    public int QuantityInStock { get; set; }
    public string? Category { get; set; }
    public string? Subcategory { get; set; }
    public string? Sku { get; set; }
    public decimal? UnitSize { get; set; }
    public string? UnitLabel { get; set; }
    public string? Ingredients { get; set; }
    public string? Origin { get; set; }
    public string? StorageInstructions { get; set; }
    public int? ShelfLifeDays { get; set; }
    public decimal? AverageRating { get; set; }
    public int? ReviewCount { get; set; }
    public string? SubstitutionGroup { get; set; }
    public NutritionFacts? Nutrition { get; set; }
    public Promotion? Promotion { get; set; }
    public ICollection<ProductAttribute> Attributes { get; set; } = [];
    
}
