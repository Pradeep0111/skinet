using API.DTOs;
using Core.Entities.OrderAggregate;

namespace API.Extensions
{
    public static class OrderMappingExtensions
    {
        public static OrderDTO ToDto(this Order order)
        {
            return new OrderDTO
            {
                Id = order.Id,
                BuyerEmail = order.BuyerEmail,
                OrderDate = order.OrderDate,
                ShippingAddress = order.ShippingAddress,
                DeliveryMethod = order.DeliveryMethod.Description,
                ShippingPrice = order.DeliveryMethod.Price,
                PaymentSummary = order.PaymentSummary,
                OrderItems = order.OrderItems.Select( x => x.ToDto()).ToList(),
                Subtotal = order.Subtotal,
                Status = order.Status.ToString(),
                PaymentIntentId = order.PaymentIntentId,
                Total = order.GetTotal()
            };
        }

        public static OrderItemDTO ToDto(this OrderItem orderItem)
        {
            return new OrderItemDTO
            {
                ProductId = orderItem.ItemOrdered.ProductId,
                ProductName = orderItem.ItemOrdered.ProductName,
                PictureUrl = orderItem.ItemOrdered.PictureUrl,
                Price = orderItem.Price,
                Quantity = orderItem.Quantity
            };
        }
    }
}
