<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use App\Models\CskhStatus;

class CskhTicket extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_tickets';

    protected $fillable = [
        'customer_id',
        'workflow_status',
        'customer_type',
        'product_text',
        'product_id',
        'issue_content',
        'handling',
        'source',
        'province_id',
        'district_id',
        'address_detail',
        'receiving_department_id',
        'current_department_id',
        'notes',
        'created_by',
        'assigned_to',
        'triage_type',
        'related_order_id',
        'related_order_code',
        'warranty_serial',
        'warranty_code',
        'closed_at',
        'created_at',
        'updated_at',
    ];

    protected $casts = [
        'product_id' => 'integer',
        'closed_at' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    public function customer(): BelongsTo
    {
        return $this->belongsTo(CskhCustomer::class, 'customer_id');
    }

    public function creator(): BelongsTo
    {
        return $this->belongsTo(User::class, 'created_by');
    }

    public function assignee(): BelongsTo
    {
        return $this->belongsTo(User::class, 'assigned_to');
    }

    public function attachments(): HasMany
    {
        return $this->hasMany(CskhTicketAttachment::class, 'cskh_ticket_id');
    }

    public function latestSolution(): HasOne
    {
        return $this->hasOne(CskhSolution::class, 'ticket_id')->latestOfMany('id');
    }

    /**
     * workflow_status -> cskh_status.code
     * Dùng để lấy description hiển thị theo trạng thái.
     */
    public function workflowStatus(): BelongsTo
    {
        return $this->belongsTo(CskhStatus::class, 'workflow_status', 'code');
    }
}
