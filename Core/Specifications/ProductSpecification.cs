using Core.Entities;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Core.Specifications
{
    public class ProductSpecification : BaseSpecification<Product>
    {
        public ProductSpecification(ProductSpecParams specParams)
            : base(x =>
            (string.IsNullOrEmpty(specParams.Search) || x.Name.ToLower().Contains(specParams.Search)) &&
            (!specParams.Brands.Any() || specParams.Brands.Contains(x.Brand)) &&
            (!specParams.Types.Any() || specParams.Types.Contains(x.Type)) &&
            (!specParams.Categories.Any() || (x.Category != null && specParams.Categories.Contains(x.Category))) &&
            (!specParams.DietaryLabels.Any() || x.Attributes.Any(attribute =>
                attribute.Kind == ProductAttributeKind.DietaryLabel && specParams.DietaryLabels.Contains(attribute.Value))) &&
            (!specParams.AllergensExcluded.Any() || !x.Attributes.Any(attribute =>
                attribute.Kind == ProductAttributeKind.Allergen && specParams.AllergensExcluded.Contains(attribute.Value))) &&
            (!specParams.MinPrice.HasValue || x.Price >= specParams.MinPrice.Value) &&
            (!specParams.MaxPrice.HasValue || x.Price <= specParams.MaxPrice.Value) &&
            (!specParams.InStock.HasValue || !specParams.InStock.Value || x.QuantityInStock > 0)
        )
        {
            ApplyPaging(specParams.PageSize * (specParams.PageIndex - 1), specParams.PageSize);
            AddInclude(x => x.Attributes);

            switch (specParams.Sort)
            {
                case "priceAsc":
                    AddOrderBy(x => x.Price);
                    break;
                case "priceDesc":
                    AddOrderByDescending(x => x.Price);
                    break;
                default: AddOrderBy(x => x.Name);
                    break;
            }
        }
    }
}
