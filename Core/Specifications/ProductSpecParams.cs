using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Core.Specifications
{
    public class ProductSpecParams : PagingParams
    {

        private List<string> _brands = [];

		public List<string> Brands
		{
			get => _brands;
			set
			{
				_brands = value.SelectMany(x => x.Split(',', StringSplitOptions.RemoveEmptyEntries)).ToList();
			}
		}

        private List<string> _types = [];

        public List<string> Types
        {
            get => _types;
            set
            {
                _types = value.SelectMany(x => x.Split(',', StringSplitOptions.RemoveEmptyEntries)).ToList();
            }
        }

        private List<string> _categories = [];

        public List<string> Categories
        {
            get => _categories;
            set
            {
                _categories = value.SelectMany(x => x.Split(',', StringSplitOptions.RemoveEmptyEntries)).ToList();
            }
        }

        private List<string> _dietaryLabels = [];

        public List<string> DietaryLabels
        {
            get => _dietaryLabels;
            set
            {
                _dietaryLabels = value.SelectMany(x => x.Split(',', StringSplitOptions.RemoveEmptyEntries)).ToList();
            }
        }

        private List<string> _allergensExcluded = [];

        public List<string> AllergensExcluded
        {
            get => _allergensExcluded;
            set
            {
                _allergensExcluded = value.SelectMany(x => x.Split(',', StringSplitOptions.RemoveEmptyEntries)).ToList();
            }
        }

        public string? Sort { get; set; }

        public decimal? MinPrice { get; set; }

        public decimal? MaxPrice { get; set; }

        public bool? InStock { get; set; }

        private string? _search;

        public string Search
        {
            get => _search ?? "";
            set => _search = value.ToLower();
        }
    }
}
