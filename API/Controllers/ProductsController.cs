using API.DTOs;
using API.Extensions;
using API.RequestHelper;
using Core.Entities;
using Core.Interfaces;
using Core.Specifications;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace API.Controllers
{
    public class ProductsController(IUnitOfWork unit) : BaseAPIController
    {

        [HttpGet]
        public async Task<ActionResult<IReadOnlyList<Product>>> GetProducts([FromQuery] ProductSpecParams specParams)
        {
            var spec = new ProductSpecification(specParams);

            return await CreatePagedResult(unit.Repository<Product>(), spec, specParams.PageIndex, specParams.PageSize);
        }
        [HttpGet("{id:int}")]
        public async Task<ActionResult<Product>> GetProduct(int id)
        {
            var product = await unit.Repository<Product>().GetByIdAsync(id);

            if (product == null) return NotFound();

            return product;
        }

        [Authorize(Roles ="Admin")]
        [HttpPost]
        public async Task<ActionResult<Product>> CreateProduct(CreateProductDTO dto)
        {
            var validationErrors = dto.GetValidationErrors();
            if (validationErrors.Count > 0) return BadRequest(new ValidationProblemDetails(validationErrors));

            var product = new Product
            {
                Name = dto.Name,
                Description = dto.Description,
                PictureUrl = dto.PictureUrl,
                Type = dto.Type,
                Brand = dto.Brand
            };
            dto.ApplyTo(product);
            unit.Repository<Product>().Add(product);

            if (await unit.Complete())
            {
                return CreatedAtAction("GetProduct", new { id = product.Id }, product);
            }

            return BadRequest("Problem creating the product");
        }

        [Authorize(Roles = "Admin")]
        [HttpPut("{id:int}")]
        public async Task<ActionResult> UpdateProduct(int id, UpdateProductDTO dto)
        {
            var validationErrors = dto.GetValidationErrors();
            if (validationErrors.Count > 0) return BadRequest(new ValidationProblemDetails(validationErrors));

            var specification = new ProductByIdSpecification(id);
            var product = await unit.Repository<Product>().GetEntityWithSpec(specification);
            if (product == null) return NotFound();

            dto.ApplyTo(product);

            if (await unit.Complete())
            {
                return NoContent();
            }

            return BadRequest("Problem updating the product");
        }

        [Authorize(Roles = "Admin")] 
        [HttpDelete("{id:int}")]
        public async Task<ActionResult> DeleteProduct(int id)
        {
            var product = await unit.Repository<Product>().GetByIdAsync(id);

            if (product == null) return NotFound("Given product does not exists");

            unit.Repository<Product>().Remove(product);

            if (await unit.Complete())
            {
                return NoContent();
            }

            return BadRequest("Problem deleting the product");

        }

        [HttpGet("brands")]
        public async Task<ActionResult<IReadOnlyList<string>>> GetBrands()
        {
            var spec = new BrandListSpecification();

            return Ok(await unit.Repository<Product>().ListAsync(spec));
        }

        [HttpGet("types")]
        public async Task<ActionResult<IReadOnlyList<string>>> GetTypes()
        {
            var spec = new TypeListSpecification();

            return Ok(await unit.Repository<Product>().ListAsync(spec));
        }
    }
}
