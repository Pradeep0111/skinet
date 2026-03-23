import { Component, inject, OnInit } from '@angular/core';
import { ShopService } from '../../Core/services/shop.service';
import { Product } from '../../shared/models/product';
import { ProductItemComponent } from './product-item/product-item.component';
import {MatDialog} from '@angular/material/dialog';
import { FiltersDialogComponent } from './filters-dialog/filters-dialog.component';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from "@angular/material/icon";
import { MatMenu, MatMenuTrigger } from "@angular/material/menu";
import { MatSelectionList, MatListOption, MatSelectionListChange } from '@angular/material/list';
import { ShopParams } from '../../shared/models/shopParams';
import { MatPaginator, PageEvent } from "@angular/material/paginator";
import { Pagination } from '../../shared/models/pagination';
import { FormsModule } from '@angular/forms';
import { EmptyStateComponent } from "../../shared/components/empty-state/empty-state.component";

@Component({
  selector: 'app-shop',
  imports: [ProductItemComponent,
    MatButton,
    MatIcon,
    MatMenu,
    MatSelectionList,
    MatMenuTrigger,
    MatListOption,
    MatPaginator,
    FormsModule, MatIconButton, EmptyStateComponent],
  templateUrl: './shop.component.html',
  styleUrl: './shop.component.scss',
})
export class ShopComponent implements OnInit {
  private shopService = inject(ShopService);
  private dialogService = inject(MatDialog);
  products?: Pagination<Product>;

  sortOptions = [
    {name : 'Alphabetical', value :'name'},
    {name : 'Price: Low to High', value :'priceAsc'},
    {name : 'Price: High to Low', value :'priceDesc'},
  ]
  shopParams = new ShopParams();
  pageSizeOptions = [5,10,15,20]

  ngOnInit(): void {
    this.initalizeShop();
  }

  initalizeShop(){
    this.shopService.getBrands();
    this.shopService.getTypes();
    this.getProducts();
  }
  resetFilters(){
    this.shopParams = new ShopParams();
    this.getProducts();
  }
  
  getProducts(){
    this.shopService.getProducts(this.shopParams).subscribe({
      next: response => this.products = response,
      error: error => console.log(error)
    })
  }

  onSearchChange(){
    this.shopParams.pageNumber = 1;
    this.getProducts();
  }

  handlePageEvent(event : PageEvent){
    this.shopParams.pageNumber = event.pageIndex + 1
    this.shopParams.pageSize = event.pageSize;
    this.getProducts()
  }

  onSortChange(event: MatSelectionListChange){
    const selectOption = event.options[0];
    if(selectOption){
      this.shopParams.sort = selectOption.value;
      this.getProducts();
    }
  }

  openFilterDialog(){
    const dialogRef = this.dialogService.open(FiltersDialogComponent, {
      minWidth: '500px',
      data:{
        selectedBrands:this.shopParams.brands,
        selectedTypes:this.shopParams.types
      }
    })
    dialogRef.afterClosed().subscribe({
      next: result =>{
        if(result){
          console.log(result);
          this.shopParams.brands = result.selectedBrands;
          this.shopParams.types = result.selectedTypes;
          this.getProducts();
        }
      }
    })
  }
}
