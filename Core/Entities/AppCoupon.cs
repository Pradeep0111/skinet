using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Core.Entities
{
    public class AppCoupon 
    {
        public required string CouponId { get; set; }
        public required string Name { get; set; }
        public decimal? AmountOff { get; set; }
        public required string PromotionCode { get; set; }
        public decimal? PercentOff { get; set; }

    }
}
