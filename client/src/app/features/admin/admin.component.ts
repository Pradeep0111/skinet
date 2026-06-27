import { AfterViewInit, Component, inject, OnInit, ViewChild } from '@angular/core';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import {
  MatTableDataSource,
  MatTable,
  MatColumnDef,
  MatHeaderCellDef,
  MatCellDef,
  MatHeaderRowDef,
  MatRowDef,
  MatHeaderRow,
  MatRow,
} from '@angular/material/table';
import { Order } from '../../shared/models/order';
import { AdminService } from '../../Core/services/admin.service';
import { OrderParams } from '../../shared/models/orderParams';
import { MatTabBody, MatTabGroup, MatTab } from "@angular/material/tabs";
import { MatFormField, MatLabel } from "@angular/material/form-field";
import { MatSelect, MatSelectChange } from "@angular/material/select";
import { MatOption } from "@angular/material/core";
import { DatePipe, CurrencyPipe } from "@angular/common";
import { MatIcon } from "@angular/material/icon";
import { MatButton, MatButtonModule } from "@angular/material/button";
import { RouterLink } from "@angular/router";
import { MatTooltip } from "@angular/material/tooltip";
import { DialogService } from '../../Core/services/dialog.service';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    MatTabGroup,
    MatTab,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatTable,
    MatColumnDef,
    MatHeaderCellDef,
    MatCellDef,
    MatHeaderRowDef,
    MatRowDef,
    MatHeaderRow,
    MatRow,
    MatPaginator,
    DatePipe,
    CurrencyPipe,
    MatIcon,
    MatButtonModule,
    RouterLink,
    MatTooltip,
],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss',
})
export class AdminComponent implements AfterViewInit, OnInit {
  displayedColumns: string[] = ['id', 'buyerEmail', 'orderDate', 'total', 'status', 'action'];
  dataSource = new MatTableDataSource<Order>([]);
  private adminService = inject(AdminService);
  private dialogService = inject(DialogService);
  orderParams = new OrderParams();
  totalItems = 0;
  statusOptions  = ['All', 'PaymentReceived', 'PaymentMismatch', 'Refunded', 'Pending'];

  @ViewChild(MatPaginator) paginator!: MatPaginator;

  ngOnInit(): void {
    this.loadOrders();
  }

  ngAfterViewInit() {
    // Server-side paging is handled manually via the paginator events.
    // Do not attach the paginator to the MatTableDataSource here.
  }

  loadOrders(){
    this.adminService.getOrders(this.orderParams).subscribe({
      next: response =>{
        if(response.data){
          this.dataSource.data = response.data;
          this.totalItems = response.count;
          this.orderParams.pageSize = response.pageSize;
        }
      }
    })
  }

  OnPageChange(event : PageEvent){
    this.orderParams.pageIndex = event.pageIndex + 1;
    this.orderParams.pageSize = event.pageSize;
    this.loadOrders();
  }

  onFilterSelect(event : MatSelectChange){
    this.orderParams.filter = event.value;
    this.orderParams.pageIndex = 1;
    this.loadOrders();
  }

  async openConfirmDialog(id : number){
    const confirmed = await this.dialogService.confirm('Confirm Refund', 'Are you sure you want to refund this order?');
    if (confirmed) {
      this.refundOrder(id);
    }
  }

  refundOrder(id:number){
    this.adminService.refundOrder(id).subscribe({
      next: order =>{
        this.dataSource.data = this.dataSource.data.map(o => o.id === id ? order : o);
      }
    })
  }
}
