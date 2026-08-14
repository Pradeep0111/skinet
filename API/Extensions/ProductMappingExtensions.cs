using API.DTOs;
using API.DTOs.Assistant;
using Core.Entities;

namespace API.Extensions;

public static class ProductMappingExtensions
{
    public static AssistantProductDto ToAssistantProductDto(this Product product)
    {
        var promotion = product.Promotion?.IsCurrentlyActive() == true
            ? new PromotionDto
            {
                SalePrice = product.Promotion.SalePrice,
                Label = product.Promotion.Label,
                StartsAt = product.Promotion.StartsAt,
                EndsAt = product.Promotion.EndsAt
            }
            : null;

        return new AssistantProductDto
        {
            Id = product.Id,
            Name = product.Name,
            Description = product.Description,
            Price = product.Price,
            EffectivePrice = promotion?.SalePrice ?? product.Price,
            PictureUrl = product.PictureUrl,
            Brand = product.Brand,
            Type = product.Type,
            Category = product.Category,
            Subcategory = product.Subcategory,
            QuantityInStock = product.QuantityInStock,
            Sku = product.Sku,
            UnitSize = product.UnitSize,
            UnitLabel = product.UnitLabel,
            Tags = GetAttributeValues(product, ProductAttributeKind.Tag),
            DietaryLabels = GetAttributeValues(product, ProductAttributeKind.DietaryLabel),
            Allergens = GetAttributeValues(product, ProductAttributeKind.Allergen),
            Ingredients = product.Ingredients,
            Nutrition = product.Nutrition == null ? null : new NutritionFactsDto
            {
                ServingSize = product.Nutrition.ServingSize,
                Calories = product.Nutrition.Calories,
                Protein = product.Nutrition.Protein,
                Carbohydrates = product.Nutrition.Carbohydrates,
                Fat = product.Nutrition.Fat,
                Fiber = product.Nutrition.Fiber,
                Sugar = product.Nutrition.Sugar,
                Sodium = product.Nutrition.Sodium
            },
            Origin = product.Origin,
            AverageRating = product.AverageRating,
            ReviewCount = product.ReviewCount,
            Promotion = promotion,
            SubstitutionGroup = product.SubstitutionGroup
        };
    }

    private static List<string> GetAttributeValues(Product product, ProductAttributeKind kind)
    {
        return product.Attributes
            .Where(attribute => attribute.Kind == kind)
            .Select(attribute => attribute.Value)
            .OrderBy(value => value)
            .ToList();
    }
}