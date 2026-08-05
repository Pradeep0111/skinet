namespace Core.Entities;

public class ProductAttribute : BaseEntity
{
    public int ProductId { get; set; }
    public required Product Product { get; set; }
    public ProductAttributeKind Kind { get; set; }
    public required string Value { get; set; }
}

public enum ProductAttributeKind
{
    Tag,
    DietaryLabel,
    Allergen
}