namespace Core.Entities;

public class Promotion
{
    public decimal SalePrice { get; set; }
    public string? Label { get; set; }
    public DateTime? StartDate { get; set; }
    public DateTime? EndDate { get; set; }
    public bool IsActive { get; set; }

    public bool IsCurrentlyActive()
    {
        if (!IsActive) return false;

        var now = DateTime.UtcNow;
        return (!StartDate.HasValue || StartDate <= now)
            && (!EndDate.HasValue || EndDate >= now);
    }
}