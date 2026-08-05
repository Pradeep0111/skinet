using Core.Entities;

namespace Core.Specifications;

public class ProductByIdSpecification : BaseSpecification<Product>
{
    public ProductByIdSpecification(int id) : base(product => product.Id == id)
    {
        AddInclude(product => product.Attributes);
    }
}