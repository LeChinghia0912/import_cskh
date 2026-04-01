<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CskhTicketTransfer extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_ticket_transfers';

    public $timestamps = false;

    protected $fillable = [
        'ticket_id',
        'to_department_id',
        'error_encountered',
        'descriptions',
        'note',
        'transferred_by',
        'created_at',
    ];

    protected $casts = [
        'created_at' => 'datetime',
    ];

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(CskhTicket::class, 'ticket_id');
    }

    public function toDepartment(): BelongsTo
    {
        return $this->belongsTo(CskhReceivingDepartment::class, 'to_department_id');
    }


    public function transferredBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'transferred_by');
    }
}

