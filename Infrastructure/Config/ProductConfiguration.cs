using System;
using Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace Infrastructure.Config;

public class ProductConfiguration : IEntityTypeConfiguration<Product>
{
    public void Configure(EntityTypeBuilder<Product> builder)
    {
        builder.Property(x => x.Price).HasColumnType("decimal(18,2)");
        builder.Property(x => x.Name).IsRequired();
        builder.Property(x => x.Category).HasMaxLength(100);
        builder.Property(x => x.Subcategory).HasMaxLength(100);
        builder.Property(x => x.Sku).HasMaxLength(100);
        builder.Property(x => x.UnitSize).HasColumnType("decimal(18,3)");
        builder.Property(x => x.UnitLabel).HasMaxLength(30);
        builder.Property(x => x.Origin).HasMaxLength(200);
        builder.Property(x => x.SubstitutionGroup).HasMaxLength(100);
        builder.Property(x => x.AverageRating).HasColumnType("decimal(3,2)");

        builder.OwnsOne(x => x.Nutrition, nutrition =>
        {
            nutrition.Property(x => x.ServingSize).HasMaxLength(100);
            nutrition.Property(x => x.Calories).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Protein).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Carbohydrates).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Fat).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Fiber).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Sugar).HasColumnType("decimal(18,2)");
            nutrition.Property(x => x.Sodium).HasColumnType("decimal(18,2)");
        });

        builder.OwnsOne(x => x.Promotion, promotion =>
        {
            promotion.Property(x => x.SalePrice).HasColumnType("decimal(18,2)");
            promotion.Property(x => x.Label).HasMaxLength(100);
        });

        builder.HasMany(x => x.Attributes)
            .WithOne(x => x.Product)
            .HasForeignKey(x => x.ProductId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
