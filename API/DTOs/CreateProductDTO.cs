using System.ComponentModel.DataAnnotations;

namespace API.DTOs
{
    public class CreateProductDTO
    {
        [Required]
        public string Name { get; set; } = string.Empty;
        [Required]
        public string Description { get; set; } = string.Empty;
        [Range(0.01, double.MaxValue, ErrorMessage = "Price must be greater than 0")]
        public decimal Price { get; set; }
        [Required] 
        public string PictureUrl { get; set; } = string.Empty;
        [Required] 
        public string Type { get; set; } = string.Empty;
        [Required] 
        public string Brand { get; set; } = string.Empty;
        [Range(0, int.MaxValue, ErrorMessage = "Quantity in stock cannot be negative")]
        public int QuantityInStock { get; set; }
        [MaxLength(100)]
        public string? Category { get; set; }
        [MaxLength(100)]
        public string? Subcategory { get; set; }
        [MaxLength(100)]
        public string? Sku { get; set; }
        public decimal? UnitSize { get; set; }
        [MaxLength(30)]
        public string? UnitLabel { get; set; }
        public string? Ingredients { get; set; }
        [MaxLength(200)]
        public string? Origin { get; set; }
        public string? StorageInstructions { get; set; }
        public string? ShelfLifeGuidance { get; set; }
        [Range(0, 5)]
        public decimal? AverageRating { get; set; }
        [Range(0, int.MaxValue)]
        public int? ReviewCount { get; set; }
        [MaxLength(100)]
        public string? SubstitutionGroup { get; set; }
        public List<string> Tags { get; set; } = [];
        public List<string> DietaryLabels { get; set; } = [];
        public List<string> Allergens { get; set; } = [];
        public ProductNutritionDto? Nutrition { get; set; }
        public ProductPromotionDto? Promotion { get; set; }
    }

    public class ProductNutritionDto
    {
        public string? ServingSize { get; set; }
        public decimal? Calories { get; set; }
        public decimal? Protein { get; set; }
        public decimal? Carbohydrates { get; set; }
        public decimal? Fat { get; set; }
        public decimal? Fiber { get; set; }
        public decimal? Sugar { get; set; }
        public decimal? Sodium { get; set; }
    }

    public class ProductPromotionDto
    {
        public decimal SalePrice { get; set; }
        [MaxLength(100)]
        public string? Label { get; set; }
        public DateTime? StartDate { get; set; }
        public DateTime? EndDate { get; set; }
        public bool IsActive { get; set; }
    }
}
