using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddPendingModelChanges : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "ShelfLifeGuidance",
                table: "Products");

            migrationBuilder.RenameColumn(
                name: "Promotion_StartDate",
                table: "Products",
                newName: "Promotion_StartsAt");

            migrationBuilder.RenameColumn(
                name: "Promotion_EndDate",
                table: "Products",
                newName: "Promotion_EndsAt");

            migrationBuilder.AddColumn<int>(
                name: "ShelfLifeDays",
                table: "Products",
                type: "int",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "ShelfLifeDays",
                table: "Products");

            migrationBuilder.RenameColumn(
                name: "Promotion_StartsAt",
                table: "Products",
                newName: "Promotion_StartDate");

            migrationBuilder.RenameColumn(
                name: "Promotion_EndsAt",
                table: "Products",
                newName: "Promotion_EndDate");

            migrationBuilder.AddColumn<string>(
                name: "ShelfLifeGuidance",
                table: "Products",
                type: "nvarchar(max)",
                nullable: true);
        }
    }
}
