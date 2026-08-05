using API.DTOs;
using Core.Entities;

namespace API.Extensions;

public static class ProductUpsertMappingExtensions
{
    public static void ApplyTo(this CreateProductDTO dto, Product product)
    {
        product.Name = dto.Name;
        product.Description = dto.Description;
        product.Price = dto.Price;
        product.PictureUrl = dto.PictureUrl;
        product.Type = dto.Type;
        product.Brand = dto.Brand;
        product.QuantityInStock = dto.QuantityInStock;
        product.Category = dto.Category;
        product.Subcategory = dto.Subcategory;
        product.Sku = dto.Sku;
        product.UnitSize = dto.UnitSize;
        product.UnitLabel = dto.UnitLabel;
        product.Ingredients = dto.Ingredients;
        product.Origin = dto.Origin;
        product.StorageInstructions = dto.StorageInstructions;
        product.ShelfLifeGuidance = dto.ShelfLifeGuidance;
        product.AverageRating = dto.AverageRating;
        product.ReviewCount = dto.ReviewCount;
        product.SubstitutionGroup = dto.SubstitutionGroup;
        product.Nutrition = dto.Nutrition == null ? null : new NutritionFacts
        {
            ServingSize = dto.Nutrition.ServingSize,
            Calories = dto.Nutrition.Calories,
            Protein = dto.Nutrition.Protein,
            Carbohydrates = dto.Nutrition.Carbohydrates,
            Fat = dto.Nutrition.Fat,
            Fiber = dto.Nutrition.Fiber,
            Sugar = dto.Nutrition.Sugar,
            Sodium = dto.Nutrition.Sodium
        };
        product.Promotion = dto.Promotion == null ? null : new Promotion
        {
            SalePrice = dto.Promotion.SalePrice,
            Label = dto.Promotion.Label,
            StartDate = dto.Promotion.StartDate,
            EndDate = dto.Promotion.EndDate,
            IsActive = dto.Promotion.IsActive
        };

        product.Attributes.Clear();
        AddAttributes(product, dto.Tags, ProductAttributeKind.Tag);
        AddAttributes(product, dto.DietaryLabels, ProductAttributeKind.DietaryLabel);
        AddAttributes(product, dto.Allergens, ProductAttributeKind.Allergen);
    }

    public static Dictionary<string, string[]> GetValidationErrors(this CreateProductDTO dto)
    {
        var errors = new Dictionary<string, string[]>();

        if (dto.UnitSize is <= 0)
            errors[nameof(dto.UnitSize)] = ["Unit size must be greater than zero."];

        if (dto.Promotion != null)
        {
            if (dto.Promotion.SalePrice <= 0 || dto.Promotion.SalePrice > dto.Price)
                errors[nameof(dto.Promotion.SalePrice)] = ["Sale price must be greater than zero and cannot exceed the regular price."];

            if (dto.Promotion.StartDate.HasValue && dto.Promotion.EndDate.HasValue
                && dto.Promotion.EndDate < dto.Promotion.StartDate)
                errors[nameof(dto.Promotion.EndDate)] = ["Promotion end date must be on or after its start date."];
        }

        if (dto.Nutrition != null && HasNegativeValue(dto.Nutrition))
            errors[nameof(dto.Nutrition)] = ["Nutrition values cannot be negative."];

        return errors;
    }

    private static void AddAttributes(Product product, IEnumerable<string> values, ProductAttributeKind kind)
    {
        foreach (var value in values.Where(value => !string.IsNullOrWhiteSpace(value))
                     .Select(value => value.Trim())
                     .Distinct(StringComparer.OrdinalIgnoreCase))
        {
            product.Attributes.Add(new ProductAttribute
            {
                Product = product,
                Kind = kind,
                Value = value
            });
        }
    }

    private static bool HasNegativeValue(ProductNutritionDto nutrition)
    {
        return nutrition.Calories < 0
            || nutrition.Protein < 0
            || nutrition.Carbohydrates < 0
            || nutrition.Fat < 0
            || nutrition.Fiber < 0
            || nutrition.Sugar < 0
            || nutrition.Sodium < 0;
    }
}